"""
Health center model signals.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from applications.globals.models import ExtraInfo
from notification.views import healthcare_center_notif

from .models import Present_Stock, Required_medicine

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Present_Stock)
def check_low_stock_alert(sender, instance, **kwargs):
    """
    Keep required-medicine table in sync and send low-stock alerts to compounders.
    """
    medicine = instance.medicine_id
    threshold = medicine.threshold or 0

    total_quantity = sum(
        Present_Stock.objects.filter(medicine_id=medicine).values_list("quantity", flat=True)
    )

    if total_quantity <= threshold:
        req, _ = Required_medicine.objects.get_or_create(
            medicine_id=medicine,
            defaults={"quantity": total_quantity, "threshold": threshold},
        )
        req.quantity = total_quantity
        req.threshold = threshold
        req.save(update_fields=["quantity", "threshold"])

        # Send notification best-effort; never block stock save.
        try:
            compounders = ExtraInfo.objects.select_related("user").filter(user_type="compounder")
            for compounder in compounders:
                healthcare_center_notif(
                    compounder.user,
                    compounder.user,
                    "med_notif",
                    "",
                )
        except Exception:
            logger.exception("Low stock notification dispatch failed")
    else:
        Required_medicine.objects.filter(medicine_id=medicine).delete()
