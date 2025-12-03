from flask import Flask, request, jsonify
from datetime import datetime
from models import db, Member, MemberBirthData, EnergyMap
from utils_energy import get_sun_sign
import os


def create_app():
    app = Flask(__name__)

    # Use Render DATABASE_URL if present, else writable /tmp sqlite
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:////tmp/aidoshop.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Ensure tables exist once per process (Flask 3 safe)
    app._db_initialized = False

    @app.before_request
    def initialize_database_once():
        if not app._db_initialized:
            with app.app_context():
                db.create_all()
            app._db_initialized = True
            app.logger.info("Database tables ensured on first request.")

    @app.route("/")
    def index():
        return "AIDOShop backend is running."

    @app.route("/api/member-intake", methods=["POST"])
    def member_intake():
        data = request.get_json(force=True) or {}
        app.logger.info(f"Member intake payload: {data}")

        try:
            # ---------------------------------------------------------
            # 1. BASIC FIELDS
            # ---------------------------------------------------------
            raw_email = (data.get("email") or "").strip().lower()
            if not raw_email:
                raise ValueError("Missing email in payload")

            full_name = (data.get("full_name") or "").strip()
            gender = (data.get("gender") or "").strip() or None

            # Focus areas can be list or string
            fa = data.get("focus_areas")
            if isinstance(fa, list):
                focus_areas = ",".join([str(x) for x in fa if x])
            elif fa:
                focus_areas = str(fa).strip()
            else:
                focus_areas = None

            consent_to_emails = bool(data.get("consent_to_emails", True))

            # ---------------------------------------------------------
            # 2. SOURCE + IP + COUNTRY
            # ---------------------------------------------------------
            # Source page: prefer explicit field, fallback to Referer
            source_page = (data.get("source_page") or "").strip()
            if not source_page:
                ref = request.headers.get("Referer")
                source_page = ref.strip() if ref else None

            # IP address via X-Forwarded-For (Render) then remote_addr
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            if forwarded_for:
                ip_address = forwarded_for.split(",")[0].strip()
            else:
                ip_address = request.remote_addr

            country_code = (data.get("country_code") or "").upper() or None

            # ---------------------------------------------------------
            # 3. UPSERT MEMBER BY EMAIL
            # ---------------------------------------------------------
            member = Member.query.filter_by(email=raw_email).first()

            if member:
                # Update existing member
                if full_name:
                    member.full_name = full_name
                if gender:
                    member.gender = gender

                member.consent_to_emails = consent_to_emails

                if focus_areas:
                    member.focus_areas = focus_areas

                if source_page:
                    member.source_page = source_page
                if ip_address:
                    member.ip_address = ip_address
                if country_code:
                    member.country_code = country_code

            else:
                # Create new member
                member = Member(
                    full_name=full_name or raw_email,
                    email=raw_email,
                    gender=gender,
                    consent_to_emails=consent_to_emails,
                    focus_areas=focus_areas,
                    source_page=source_page,
                    ip_address=ip_address,
                    country_code=country_code,
                )
                db.session.add(member)
                db.session.flush()  # get member.id

            # ---------------------------------------------------------
            # 4. DOB / TOB PARSING
            # ---------------------------------------------------------
            dob_raw = (data.get("date_of_birth") or "").strip()
            if not dob_raw:
                raise ValueError("Missing date_of_birth in payload")

            dob = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d-%b-%y"):
                try:
                    dob = datetime.strptime(dob_raw, fmt).date()
                    break
                except ValueError:
                    continue

            if dob is None:
                raise ValueError(f"Unsupported date format: {dob_raw}")

            tob = None
            tob_raw = (data.get("time_of_birth") or "").strip()
            if tob_raw:
                for tfmt in ("%H:%M", "%H:%M:%S"):
                    try:
                        tob = datetime.strptime(tob_raw, tfmt).time()
                        break
                    except ValueError:
                        continue

            birth_city = data.get("birth_city")
            time_zone = data.get("time_zone")

            # ---------------------------------------------------------
            # 5. UPSERT BIRTH DATA
            # ---------------------------------------------------------
            birth = MemberBirthData.query.filter_by(member_id=member.id).first()
            if birth is None:
                birth = MemberBirthData(
                    member_id=member.id,
                    date_of_birth=dob,
                    time_of_birth=tob,
                    birth_city=birth_city,
                    time_zone=time_zone,
                )
                db.session.add(birth)
            else:
                birth.date_of_birth = dob
                birth.time_of_birth = tob
                birth.birth_city = birth_city
                birth.time_zone = time_zone

            # ---------------------------------------------------------
            # 6. UPSERT ENERGY MAP
            # ---------------------------------------------------------
            energy_type = get_sun_sign(dob)

            energy = EnergyMap.query.filter_by(member_id=member.id).first()
            if energy is None:
                energy = EnergyMap(
                    member_id=member.id,
                    energy_type=energy_type,
                    notes=f"Auto-generated based on {energy_type}",
                )
                db.session.add(energy)
            else:
                energy.energy_type = energy_type
                energy.notes = f"Auto-updated based on {energy_type}"

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
