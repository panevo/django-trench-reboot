from pyotp import HOTP


class CreateHOTPCommand:
    @staticmethod
    def execute(secret: str, counter: int) -> HOTP:
        return HOTP(secret)


create_hotp_command = CreateHOTPCommand.execute
