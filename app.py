from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    session,
    Response,
)
from datetime import datetime
from functools import wraps
from models import db, Member, MemberBirthData, EnergyMap
from utils_energy import get_sun_sign
import os
import csv
import io


def create_app():
    app = Flask(__name__)

    # ---------- CONFIG ----------
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///aidoshop.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Needed for login sessions
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-env")

    # Simple admin credentials (you can override in Render env)
    app.config["ADMIN_USERNAME"] = os.environ.get("ADMIN_USERNAME", "aido")
    app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "aido123!")

    db.init_app(app)

    # ---------- DB INIT (Flask 3 safe) ----------
    app._db_initialized = False

    @app.before_request
    def initialize_database_once():
        if not app._db_initialized:
            with app.app_context():
                db.create_all()
            app._db_initialized = True
            app.logger.info("Database tables created/verified on first request.")
    # --------------------------------------------

    # ---------- SIMPLE LOGIN PROTECTION ----------
    def login_required(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not session.get("admin_logged_in"):
                return redirect(url_for("admin_login", next=request.path))
            return view_func(*args, **kwargs)

        return wrapped
    # --------------------------------------------

    @app.route("/")
    def index():
        return "AIDOShop backend is running."

    # ========== ADMIN LOGIN / LOGOUT ==========
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            if (
                username == app.config["ADMIN_USERNAME"]
                and password == app.config["ADMIN_PASSWORD"]
            ):
                session["admin_logged_in"] = True
                next_url = request.args.get("next") or url_for("admin_members")
                return redirect(next_url)
            else:
                error = "Invalid username or password."

        return render_template("admin_login.html", error=error)

    @app.route("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("admin_login"))

    # ========== ADMIN DASHBOARD ==========
    @app.route("/admin/members")
    @login_required
    def admin_members():
        # Filters from query string
        focus_filter = request.args.get("focus", "").strip()
        search = request.args.get("search", "").strip()

        q = Member.query

        # Filter by focus area (e.g. Career / Wealth / Health)
        if focus_filter:
            q = q.filter(Member.focus_areas.ilike(f"%{focus_filter}%"))

        # Simple text search over name, email, source_page
        if search:
            like = f"%{search}%"
            q = q.filter(
                db.or_(
                    Member.full_name.ilike(like),
                    Member.email.ilike(like),
                    Member.source_page.ilike(like),
                )
            )

        q = q.order_by(Member.created_at.desc())
        members = q.limit(1000).all()  # safety limit

        # Aggregate focus_areas for chart
        focus_counts = {}
        for m in members:
            if not m.focus_areas:
                continue
            for raw_item in m.focus_areas.split(","):
                label = raw_item.strip()
                if not label:
                    continue
                focus_counts[label] = focus_counts.get(label, 0) + 1

        chart_labels = list(focus_counts.keys())
        chart_values = [focus_counts[label] for label in chart_labels]

        return render_template(
            "admin_members.html",
            members=members,
            chart_labels=chart_labels,
            chart_values=chart_values,
            current_focus=focus_filter,
            current_search=search,
        )

    # ========== EXPORT TO CSV (Excel) ==========
    @app.route("/admin/members/export")
    @login_required
    def export_members():
        q = Member.query.order_by(Member.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "id",
                "full_name",
                "email",
                "gender",
                "focus_areas",
                "source_page",
                "ip_address",
                "country_code",
                "consent_to_emails",
                "created_at",
            ]
        )

        for m in q:
            writer.writerow(
                [
                    m.id,
                    m.full_name,
                    m.email,
                    m.gender,
                    m.focus_areas or "",
                    getattr(m, "source_page", "") or "",
                    getattr(m, "ip_address", "") or "",
                    getattr(m, "country_code", "") or "",
                    m.consent_to_emails,
                    m.created_at.isoformat() if m.created_at else "",
                ]
            )

        csv_data = output.getvalue()
        output.close()

        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=members.csv"},
        )

    # ========== API: MEMBER INTAKE ==========
    @app.route("/api/member-intake", methods=["POST"])
    def member_intake():
        data = request.get_json(force=True)
        app.logger.info(f"Member intake payload: {data}")

        try:
            # Focus areas can be list or single string
            focus_raw = data.get("focus_areas", [])
            if isinstance(focus_raw, list):
                focus_areas = ",".join([str(x) for x in focus_raw])
            else:
                focus_areas = str(focus_raw) if focus_raw else ""

            source_page = data.get("source_page")

            # Try to capture IP (Render/Proxy + direct)
            ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr or "")
            if ip_addr and "," in ip_addr:
                ip_addr = ip_addr.split(",")[0].strip()

            # 1. Create member
            member = Member(
                full_name=data["full_name"],
                email=data["email"],
                gender=data.get("gender"),
                consent_to_emails=bool(data.get("consent_to_emails", True)),
                focus_areas=focus_areas,
                source_page=source_page,
                ip_address=ip_addr,
                # country_code left as None for now
            )
            db.session.add(member)
            db.session.flush()  # get member.id

            # 2. Parse date of birth (be flexible with formats)
            dob_raw = data.get("date_of_birth", "").strip()
            if not dob_raw:
                raise ValueError("Missing date_of_birth in payload")

            dob = None
            # Support several common formats
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d-%b-%y"):
                try:
                    dob = datetime.strptime(dob_raw, fmt).date()
                    break
                except ValueError:
                    continue

            if dob is None:
                raise ValueError(f"Unsupported date format: {dob_raw}")

            # 3. Parse time of birth (optional)
            tob = None
            tob_raw = data.get("time_of_birth")
            if tob_raw:
                for tfmt in ("%H:%M", "%H:%M:%S"):
                    try:
                        tob = datetime.strptime(tob_raw, tfmt).time()
                        break
                    except ValueError:
                        continue

            # 4. Save birth data
            birth = MemberBirthData(
                member_id=member.id,
                date_of_birth=dob,
                time_of_birth=tob,
                birth_city=data.get("birth_city"),
                time_zone=data.get("time_zone"),
            )
            db.session.add(birth)

            # 5. Simple energy map
            energy_type = get_sun_sign(dob)
            energy = EnergyMap(
                member_id=member.id,
                energy_type=energy_type,
                notes=f"Auto-generated based on {energy_type}",
            )
            db.session.add(energy)

            db.session.commit()

            return jsonify({"status": "ok", "member_id": member.id}), 201

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Member intake error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 400

    return app


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)
