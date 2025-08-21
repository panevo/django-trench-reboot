from pyotp import HOTP


class CreateHOTPCommand:
    @staticmethod
    def execute(secret: str) -> HOTP:
        return HOTP(secret)


create_hotp_command = CreateHOTPCommand.execute
