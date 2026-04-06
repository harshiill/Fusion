
from django.db import models
from datetime import date
from django.contrib.auth.models import User

from applications.globals.models import ExtraInfo
from applications.hr2.models import EmpDependents

# Create your models here.

class DayOfWeek(models.IntegerChoices):
    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"
    SUNDAY = 6, "Sunday"


class Constants:
    DAYS_OF_WEEK = DayOfWeek.choices
    NAME_OF_PATHOLOGIST = (
        (0, 'Dr.Ajay'),
        (1, 'Dr.Rahul'),
    )

class Doctor(models.Model):
    doctor_name = models.CharField(max_length=50)
    doctor_phone = models.CharField(max_length=15)
    specialization = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.doctor_name

class Pathologist(models.Model):
    pathologist_name = models.CharField(max_length=50)
    pathologist_phone = models.CharField(max_length=15)
    specialization = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.pathologist_name

# class Complaint(models.Model):
#     user_id = models.ForeignKey(ExtraInfo,on_delete=models.CASCADE)
#     feedback = models.CharField(max_length=100, null=True, blank=False)                          #This is the feedback given by the compounder
#     complaint = models.CharField(max_length=100, null=True, blank=False)                         #Here Complaint given by user cannot be NULL!
#     date = models.DateField(auto_now=True)

class All_Medicine(models.Model):
    medicine_name = models.CharField(max_length=1000,default="NOT_SET", null=True)
    brand_name = models.CharField(max_length=1000,default="NOT_SET", null=True)
    constituents = models.TextField(default="NOT_SET",  null=True)
    manufacturer_name = models.CharField(max_length=1000,default="NOT_SET", null=True)
    threshold = models.IntegerField(default=0, null=True)
    pack_size_label = models.CharField(max_length=1000,default="NOT_SET", null=True)

    def __str__(self):
        return self.brand_name
    
class Stock_entry(models.Model):
    medicine_id = models.ForeignKey(All_Medicine, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    supplier = models.CharField(max_length=50,default="NOT_SET")
    Expiry_date = models.DateField()
    date = models.DateField(auto_now=True)
    # generic_name = models.CharField(max_length=80)

    def __str__(self):
        return self.medicine_id.medicine_name
    

class Required_medicine(models.Model):
    medicine_id = models.ForeignKey(All_Medicine,on_delete = models.CASCADE)
    quantity = models.IntegerField()
    threshold = models.IntegerField()

class Present_Stock(models.Model):
    quantity = models.IntegerField(default=0)
    stock_id = models.ForeignKey(Stock_entry,on_delete=models.CASCADE)
    medicine_id = models.ForeignKey(All_Medicine, on_delete=models.CASCADE)
    Expiry_date =models.DateField()


    # generic_name = models.CharField(max_length=80)

    def __str__(self):
        return str(self.Expiry_date)

class Doctors_Schedule(models.Model):
    doctor_id = models.ForeignKey(Doctor,on_delete=models.CASCADE)
    # pathologist_id = models.ForeignKey(Pathologist,on_delete=models.CASCADE, default=0)
    day = models.IntegerField(choices=DayOfWeek.choices)
    from_time = models.TimeField(null=True,blank=True)  
    to_time = models.TimeField(null=True,blank=True)
    room = models.IntegerField()
    date = models.DateField(auto_now=True)
    
class Pathologist_Schedule(models.Model):
    # doctor_id = models.ForeignKey(Doctor,on_delete=models.CASCADE)
    pathologist_id = models.ForeignKey(Pathologist,on_delete=models.CASCADE)
    day = models.IntegerField(choices=DayOfWeek.choices)
    from_time = models.TimeField(null=True,blank=True)
    to_time = models.TimeField(null=True,blank=True)
    room = models.IntegerField()
    date = models.DateField(auto_now=True)

class All_Prescription(models.Model):
    user_id = models.CharField(max_length=15)
    doctor_id = models.ForeignKey(Doctor, on_delete=models.CASCADE,null=True, blank=True)
    details = models.TextField(null=True)
    date = models.DateField()
    suggestions = models.TextField(null=True)
    test = models.CharField(max_length=200, null=True, blank=True)
    file_id=models.IntegerField(default=0)
    is_dependent = models.BooleanField(default=False)
    dependent_name = models.CharField(max_length=30,default="SELF")
    dependent_relation = models.CharField(max_length=20,default="SELF")
    follow_up_of = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='follow_ups',
    )
    # appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE,null=True, blank=True)

    def __str__(self):
        return self.user_id

class Prescription_followup(models.Model):
    prescription_id=models.ForeignKey(All_Prescription,on_delete=models.CASCADE)
    details = models.TextField(null=True)
    date = models.DateField()
    test = models.CharField(max_length=200, null=True, blank=True)
    suggestions = models.TextField(null=True)
    Doctor_id = models.ForeignKey(Doctor,on_delete=models.CASCADE, null=True, blank=True)
    file_id=models.IntegerField(default=0)
class All_Prescribed_medicine(models.Model):
    prescription_id = models.ForeignKey(All_Prescription,on_delete=models.CASCADE)
    medicine_id = models.ForeignKey(All_Medicine,on_delete=models.CASCADE)
    stock = models.ForeignKey(Present_Stock,on_delete=models.CASCADE,null=True)
    prescription_followup_id = models.ForeignKey(Prescription_followup,on_delete=models.CASCADE,null=True)
    quantity = models.IntegerField(default=0)
    days = models.IntegerField(default=0)
    times = models.IntegerField(default=0)
    revoked = models.BooleanField(default=False)
    revoked_date = models.DateField(null=True)
    revoked_prescription = models.ForeignKey(Prescription_followup,on_delete=models.CASCADE,null=True,related_name="revoked_priscription")

    def __str__(self):
        return self.medicine_id.medicine_name
class Required_tabel_last_updated(models.Model):
    date=models.DateField()
class files(models.Model):
    file_data = models.BinaryField()

class medical_relief(models.Model):
    description = models.CharField(max_length=200)
    file = models.FileField(upload_to='medical_files/') 
    file_id=models.IntegerField(default=0)
    compounder_forward_flag = models.BooleanField(default=False)
    acc_admin_forward_flag = models.BooleanField(default=False)


class MedicalRelief(models.Model):
    STATUS_SUBMITTED = "SUBMITTED"
    STATUS_PHC_REVIEWED = "PHC_REVIEWED"
    STATUS_ACCOUNTS_REVIEWED = "ACCOUNTS_REVIEWED"
    STATUS_SANCTIONED = "SANCTIONED"
    STATUS_REJECTED = "REJECTED"
    STATUS_PAID = "PAID"

    STATUS_CHOICES = (
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_PHC_REVIEWED, "PHC Reviewed"),
        (STATUS_ACCOUNTS_REVIEWED, "Accounts Reviewed"),
        (STATUS_SANCTIONED, "Sanctioned"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_PAID, "Paid"),
    )

    user_id = models.ForeignKey(ExtraInfo, on_delete=models.CASCADE, related_name="medical_relief_requests")
    description = models.CharField(max_length=300)
    file = models.FileField(upload_to="medical_relief/", null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    reviewed_by = models.ForeignKey(
        ExtraInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medical_relief_reviewed",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"MedicalRelief {self.id} - {self.status}"


class Announcement(models.Model):
    message = models.CharField(max_length=200)
    ann_date = models.DateField(auto_now_add=True)
    file = models.FileField(upload_to="announcements/", null=True, blank=True)
    created_by = models.ForeignKey(ExtraInfo, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Announcement {self.id} - {self.ann_date}"
    
    
class MedicalProfile(models.Model):
    user_id = models.ForeignKey(ExtraInfo, on_delete=models.CASCADE, null=True) 
    date_of_birth = models.DateField()
    gender_choices = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    gender = models.CharField(max_length=1, choices=gender_choices)
    blood_type_choices = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]
    blood_type = models.CharField(max_length=3, choices=blood_type_choices)
    height = models.DecimalField(max_digits=5, decimal_places=2)  
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    blood_group = models.CharField(max_length=5, null=True, blank=True)
    allergies = models.TextField(null=True, blank=True)
    chronic_conditions = models.TextField(null=True, blank=True)
    emergency_contact = models.CharField(max_length=20, null=True, blank=True)

