from __future__ import annotations

from enum import StrEnum

import httpx

TGTG_BASE_URL = httpx.URL("https://apptoogoodtogo.com/api/")


class TgtgApi(StrEnum):
    APP_ON_STARTUP = "app/v1/onStartup"
    USER_DATA_EXPORT = "gdpr/v1/{}/exportUserData"
    USER_DELETE = "gdpr/v1/{}/deleteUser"
    USER_EMAIL_CHANGE = "user/v2/emailChangeRequest"
    USER_EMAIL_STATUS = "user/v2/getEmailStatus"
    USER_PROFILE = "user/v2/profileDetails"
    USER_SET_DEVICE = "user/device/v1/setUserDevice"

    AUTH_BY_EMAIL = "auth/v5/authByEmail"
    AUTH_LOGOUT = "auth/v5/logout"
    AUTH_BY_PIN = "auth/v5/authByRequestPin"
    AUTH_BY_POLLING = "auth/v5/authByRequestPollingId"
    TOKEN_REFRESH = "token/v1/refresh"

    INVITATION_STATUS = "invitation/v1/order/{}"
    INVITATION_LINK_STATUS = "invitation/v1/order/fromLink/{}"
    INVITATION_ORDER_STATUS = "invitation/v1/order/getOrder/{}"
    INVITATION_ACCEPT = "invitation/v1/{}/accept"
    INVITATION_CREATE = "invitation/v1/order/{}/createOrEnable"
    INVITATION_DISABLE = "invitation/v1/{}/disable"
    INVITATION_RETURN = "invitation/v1/{}/regret"

    FAVORITES = "discover/v1/bucket"
    ITEMS = "item/v8/"

    ITEM_STATUS = "item/v8/{}"
    ITEM_FAVORITE = "user/favorite/v1/{}/update"

    ORDERS = "order/v8/"
    ORDERS_ACTIVE = "order/v8/active"

    ORDER_STATUS = "order/v8/{}"
    ORDER_ABORT = "order/v8/{}/abort"
    ORDER_CANCEL = "order/v8/{}/cancel"
    ORDER_CREATE = "order/v8/create/{}"
    ORDER_PAY = "order/v8/{}/pay"
    ORDER_PAYMENT_STATUS = "payment/v4/order/{}"

    PAYMENT_STATUS = "payment/v4/{}"
    PAYMENT_3DS = "payment/v4/{}/additionalAuthorization"

    REWARDS = "user/rewards/v2"
    REWARDS_RESERVE = "user/rewards/v2/order/{}/reserve"

    SUPPORT_REQUEST = "support/v2/consumer/"

    VOUCHERS_ACTIVE = "voucher/v4/active"
    VOUCHERS_USED = "voucher/v4/used"

    VOUCHER_ADD = "voucher/v4/add"
    VOUCHER_STATUS = "voucher/v4/{}"

    @property
    def include_credentials(self) -> bool:
        return self not in {TgtgApi.AUTH_BY_EMAIL, TgtgApi.AUTH_BY_POLLING}
