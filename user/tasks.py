from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, name='send_contact_email_task')
def send_contact_email_task(self, subject=None, message=None, from_email=None):
    try:
        if not all([subject, message, from_email]):
            raise ValueError("Missing required email parameters")
            
        send_mail(
            subject,
            message,
            from_email,
            [settings.EMAIL_HOST_USER],  # Send to admin email
            fail_silently=False,
        )
        logger.info(f"Email sent successfully: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise self.retry(exc=e, countdown=60)


