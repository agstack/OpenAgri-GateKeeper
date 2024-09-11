'''
Use Case: Signals are more suited for logging events related to model changes, such as creation, update, or deletion of
Django model instances.

Granularity: Signals can be more specific, logging only when certain actions occur on models.

Decoupling: Signals offer a higher degree of decoupling since they are not tied to the request-response cycle.

Signal Registration:

The @receiver(post_save, sender=UserActivityLog) decorator is used to register the log_user_activity function as a
receiver for the post_save signal for the UserActivityLog model. This means that log_user_activity will be called every
time a UserActivityLog instance is saved.
Signal Receiver Function - log_user_activity:

This function is triggered after a UserActivityLog instance is saved (after a new record is created or an existing
record is updated).
The function checks if a new record was created (if created:). If true, it formats a log entry string with details from
the UserActivityLog instance, such as user, method, activity, timestamp, and user_timezone.
Logging the Activity:

The formatted log entry is then logged using logger.info(log_entry).
The logger named 'backend.models' is configured to handle this log. According to LOGGING configuration in
settings.py, this logger writes the logs to the file specified by the 'file' handler (user_activity.log).
'''

# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from backend.models import UserActivityLog
# import logging
#
# logger = logging.getLogger('backend.models')
#
#
# @receiver(post_save, sender=UserActivityLog)
# def log_user_activity(sender, instance, created, **kwargs):
#     if created:
#         log_entry = f"{instance.user} - {instance.method} {instance.activity} - {instance.timestamp} - {instance.user_timezone}"  # Include user_timezone here
#         logger.info(log_entry)
