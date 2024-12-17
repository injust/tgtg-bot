from __future__ import annotations


class TgtgApiError(Exception):
    pass


class TgtgAlreadyAbortedError(TgtgApiError):
    pass


class TgtgCancelDeadlineError(TgtgApiError):
    pass


class TgtgCaptchaError(TgtgApiError):
    pass


class TgtgEmailChangeError(TgtgApiError):
    pass


class TgtgItemDeletedError(TgtgApiError):
    pass


class TgtgItemDisabledError(TgtgApiError):
    pass


class TgtgLoginError(TgtgApiError):
    pass


class TgtgPaymentError(TgtgApiError):
    pass


class TgtgReservationError(TgtgApiError):
    pass


class TgtgLimitExceededError(TgtgReservationError):
    pass


class TgtgReservationBlockedError(TgtgReservationError):
    pass


class TgtgSaleClosedError(TgtgReservationError):
    pass


class TgtgSoldOutError(TgtgReservationError):
    pass


class TgtgUnauthorizedError(TgtgApiError):
    pass


class TgtgValidationError(TgtgApiError):
    pass
