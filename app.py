from flask import Flask, request, jsonify
from datetime import datetime
from models import db, Member, MemberBirthData, EnergyMap
from utils_energy import get_sun_sign
import os


def create_app():
    app = Flask(__name__)

    # ---------------------------------------------------------
    # DATABASE CONFIG
    # ---------------------------------------------------------
    # 1) If DATABASE_URL is set (e.g. Postgres on Render), use that.
    # 2) Otherwise, fall back to an SQLite file in /tmp (writable on Render).
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        # Use a writable temp location for SQLite (ephemeral but fine for testing)
        sqlite_path = "/tmp/aidoshop.db"
        db_url = f"sqlite:///{sqlite_path}"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Log which DB we are using
    with app.app_context():
        app.logger.info(f"SQLALCHEMY_DATABASE_URI in use: {db.engine.url}")
        app.logger.info(f"DB file path (if sqlite): {getattr(db.engine.url, 'database', None)}")

    # ----------------- FLASK 3 SAFE DB INITIALISER -----------------
    # before_first_request is removed in Flask 3, so we do a one-time
    # init using before_request + flag.
    app._db_initialized = False

    @app.before_request
    def initialize_database_once():
        if not app._db_initialized:
            with app.app_context():
                db.create_all()
            app._db_initialized = True
            app.logger.info("Database tables created/verified on first request.")
    # ----------------------------------------------------------------

    @app.route("/")
    def index():
        return "AIDOShop backend is running."

    @app.route("/api/member-intake", methods=["POST"])
    def member_intake():
        data = request.get_json(force=True)
        app.logger.info(f"Member intake payload: {data}")

        try:
            # 1. Create member
            member = Member(
                full_name=data["full_name"],
                email=data["email"],
                gender=data.get("gender"),
                consent_to_emails=bool(data.get("consent_to_emails", True)),
                # focus_areas handled in a moment
            )

            # Optional focus_areas: expect a string like "Career,Wealth"
            focus_areas = data.get("focus_areas")
            if isinstance(focus_areas, list):
                # In case we ever send a list, join into a string
                focus_areas = ",".join(focus_areas)
            member.focus_areas = focus_areas

            db.session.add(member)
            db.session.flush()  # get member.id

            # 2. Parse date of birth (be flexible with formats)
            dob_raw = data.get("date_of_birth", "").strip()
            if not dob_raw:
                raise ValueError("Missing date_of_birth in payload")

            dob = None
            # Added %m/%d/%Y and %d-%b-%y to support formats like 12/13/2019 and 02-Oct-82
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
