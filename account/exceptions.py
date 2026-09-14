class AccountException(Exception):
    """Base exception for account domain errors."""


class OTPException(AccountException):
    """Base exception for OTP-related failures."""


class InvalidOtpException(OTPException):
    """Raised when the provided OTP is invalid."""


class ExpiredOtpException(OTPException):
    """Raised when an OTP has expired."""


class OTPRateLimitExceededException(OTPException):
    """Raised when OTP requests exceed the allowed rate."""


class SMSProviderException(AccountException):
    """Raised when the SMS provider cannot deliver a message."""


class WhatsAppProviderException(AccountException):
    """Raised when the WhatsApp provider cannot deliver a message."""


class WhatsAppUnavailableException(WhatsAppProviderException):
    """Raised when the recipient number is not reachable on WhatsApp."""


class AuthenticationException(AccountException):
    """Raised when authentication or session validation fails."""


class PhoneAlreadyExistsException(AccountException):
    """Raised when attempting to use a duplicate phone number."""


class PasswordResetException(AccountException):
    """Raised when password reset flow cannot be completed."""


class SessionValidationException(AccountException):
    """Raised when a session token is missing or invalid."""

