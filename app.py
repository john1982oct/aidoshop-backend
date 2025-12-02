from flask import Flask, request, jsonify
from datetime import datetime
from models import db, Member, MemberBirthData, EnergyMap
from utils_energy import get_sun_sign
import os

def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///aidoshop.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    @app.before_first_request
    def init_db():
        # this runs on the first request in Render/gunicorn
        db.create_all()

    @app.route("/")
    def index():
        return "AIDOShop backend is running."

    @app.route("/api/member-intake", methods=["POST"])
    def member_intake():
        data = request.get_json(force=True)
        app.logger.info(f"Member intake payload: {data}")

        try:
            # 1. Member
            member = Member(
                full_name=data["full_name"],
                email=data["email"],
                gender=data.get("gender"),
                consent_to_emails=bool(data.get("consent_to_emails", True)),
            )
            db.session.add(member)
            db.session.flush()  # get member.id

            # 2. DOB parsing (be flexible with format)
            dob_raw = data["date_of_birth"]

            dob = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    dob = datetime.strptime(dob_raw, fmt).date()
                    break
                except ValueError:
                    continue

            if dob is None:
                raise ValueError(f"Unsupported date format: {dob_raw}")

            tob = None
            tob_raw = data.get("time_of_birth")
            if tob_raw:
                # allow "HH:MM" or "HH:MM:SS"
                for tfmt in ("%H:%M", "%H:%M:%S"):
                    try:
                        tob = datetime.strptime(tob_raw, tfmt).time()
                        break
                    except ValueError:
                        continue

            birth = MemberBirthData(
                member_id=member.id,
                date_of_birth=dob,
                time_of_birth=tob,
                birth_city=data.get("birth_city"),
                time_zone=data.get("time_zone"),
            )
            db.session.add(birth)

            # 3. Simple energy map
            energy_type = get_sun_sign(dob)
            energy = EnergyMap(
                member_id=member.id,
                energy_type=energy_type,
                notes=f"Auto-generated: {energy_type}",
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
