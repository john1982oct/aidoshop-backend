from flask import Flask, request, jsonify
from datetime import datetime
from models import db, Member, MemberBirthData, EnergyMap
from utils_energy import get_sun_sign
import os

def create_app():
    app = Flask(__name__)

    # Render will provide DATABASE_URL automatically when you use Postgres
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///aidoshop.db"   # fallback for testing
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    @app.route("/")
    def index():
        return "AIDOShop backend is running."

    @app.route("/api/member-intake", methods=["POST"])
    def member_intake():
        data = request.get_json(force=True)

        try:
            # 1. Member basic data
            member = Member(
                full_name=data["full_name"],
                email=data["email"],
                gender=data.get("gender"),
                consent_to_emails=bool(data.get("consent_to_emails", True)),
            )
            db.session.add(member)
            db.session.flush()  # get user ID

            # 2. Birth data
            dob = datetime.strptime(data["date_of_birth"], "%Y-%m-%d").date()
            tob = None
            if data.get("time_of_birth"):
                tob = datetime.strptime(data["time_of_birth"], "%H:%M").time()

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
            return jsonify({"status": "error", "message": str(e)}), 400

    return app


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)
