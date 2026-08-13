import hmac

from app.core.config import settings as env_settings
from app.core.security import hash_password, verify_password
from app.models.user import AuthResponse, LoginRequest, UserCreate
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.services.errors import InvalidCredentialsError


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository | None = None,
        session_repository: SessionRepository | None = None,
    ) -> None:
        self.user_repository = user_repository or UserRepository()
        self.session_repository = session_repository or SessionRepository()

    def signup(self, payload: UserCreate) -> AuthResponse:
        required_code = env_settings.signup_invite_code
        if required_code and not hmac.compare_digest(payload.invite_code or "", required_code):
            raise InvalidCredentialsError("Invalid or missing invite code")

        record = self.user_repository.create(str(payload.email), hash_password(payload.password))
        token = self.session_repository.create(record.id)
        return AuthResponse(user=record.to_user(), token=token)

    def login(self, payload: LoginRequest) -> AuthResponse:
        record = self.user_repository.get_by_email(str(payload.email))
        if record is None or not verify_password(payload.password, record.password_hash):
            raise InvalidCredentialsError("Invalid email or password")

        token = self.session_repository.create(record.id)
        return AuthResponse(user=record.to_user(), token=token)

    def logout(self, token: str) -> None:
        self.session_repository.delete(token)
