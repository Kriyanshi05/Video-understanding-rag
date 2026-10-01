from stages.celery_app import celery_app


# Throwaway test task to verify the worker pipeline works end-to-end.
@celery_app.task
def add_numbers(x, y):
    return x + y
