import sentry_sdk


def init_sentry():
    sentry_sdk.init(
        dsn="https://8272984d93d4960a2578d8292b08d2f7@o4506850555002880.ingest.us.sentry.io/4509903664971776",
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        send_default_pii=True,
    )