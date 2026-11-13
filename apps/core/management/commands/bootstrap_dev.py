from django.core.management.base import BaseCommand

from apps.core.models import Tenant

DEMO_INFO = """Sai Demo Clinic (sirf testing ke liye nakli jaankari), Andheri West, Mumbai.
Timing: Monday se Saturday, subah 10 baje se shaam 7 baje. Sunday band.
Doctors: Dr. Mehta (General physician), Dr. Rao (Dentist).
Fees: General consultation Rs 500. Dental checkup Rs 600. Teeth cleaning Rs 1500.
Parking: building ke piche free parking hai.
Payment: UPI aur cash dono chalte hain.
Booking: naam, number aur pasandida din aur samay batayein, team confirm karegi.
"""


class Command(BaseCommand):
    help = "Testing ke liye Demo Clinic tenant banata hai (dobara chalane par duplicate nahi)."

    def handle(self, *args, **opts):
        tenant, created = Tenant.objects.get_or_create(
            wa_phone_number_id="123",
            defaults={"name": "Demo Clinic", "business_type": Tenant.BusinessType.CLINIC},
        )
        if not tenant.business_info:
            tenant.business_info = DEMO_INFO
            tenant.save(update_fields=["business_info"])
        status = "ban gaya" if created else "pehle se hai"
        self.stdout.write(f"Tenant '{tenant.name}' (id={tenant.pk}) {status}.")
        self.stdout.write('Ab chalao: python manage.py simulate_message "Hi"')
