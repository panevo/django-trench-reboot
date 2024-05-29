from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from trench.views import MFAFirstStepMixin, MFASecondStepMixin, MFAStepMixin, User


class MFAJWTView(MFAStepMixin):
    def _successful_authentication_response(self, user: User) -> Response:
        refresh_token = RefreshToken.for_user(user=user)
        access_token = AccessToken.for_user(user=user)
        return Response(data={"refresh": str(refresh_token), "access": str(access_token)})


class MFAFirstStepJWTView(MFAJWTView, MFAFirstStepMixin):
    pass


class MFASecondStepJWTView(MFAJWTView, MFASecondStepMixin):
    pass
