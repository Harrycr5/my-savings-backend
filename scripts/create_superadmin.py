import asyncio
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import func, or_, select

from app.core.security import hash_password
from app.db.models import load_models
from app.db.session import AsyncSessionLocal, engine
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate


async def create_superadmin(data: UserCreate) -> None:
    load_models()

    email = str(data.email).lower()
    username = data.username.upper()

    try:
        async with AsyncSessionLocal.begin() as session:
            existing_user = await session.scalar(
                select(User).where(
                    or_(
                        User.email == email,
                        func.upper(User.username) == username,
                    )
                )
            )

            if existing_user is not None:
                print("El correo o username ya existe. No se modificó.")
                return

            profile = await session.scalar(select(Profile).where(Profile.code == "superadmin"))

            if profile is None:
                profile = Profile(
                    code="superadmin",
                    name="Superadministrador",
                    description="Acceso completo al sistema.",
                    is_active=True,
                )
                session.add(profile)

            elif not profile.is_active:
                print("El perfil superadmin está desactivado.")
                return

            password_hash = await hash_password(data.password.get_secret_value())

            session.add(
                User(
                    email=email,
                    username=username,
                    name=data.name,
                    last_name=data.last_name,
                    password_hash=password_hash,
                    is_active=True,
                    is_admin=True,
                    profile=profile,
                )
            )

        print("Superadmin creado correctamente.")

    finally:
        await engine.dispose()


def main() -> None:
    email = input("Correo: ").strip()
    username = input("Username: ").strip()
    name = input("Nombre: ").strip()
    last_name = input("Apellidos: ").strip()

    password = getpass("Contraseña: ")
    confirmation = getpass("Repite la contraseña: ")

    if password != confirmation:
        print("Las contraseñas no coinciden.")
        return

    try:
        data = UserCreate(
            email=email,
            username=username,
            name=name,
            last_name=last_name,
            password=password,
        )
    except ValidationError as exc:
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"])
            print(f"{field}: {error['msg']}")
        return

    asyncio.run(create_superadmin(data))


if __name__ == "__main__":
    main()
