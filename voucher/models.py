from django.db import models

# Create your models here.
class Plan(models.Model):
    name = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    has_passive_income = models.BooleanField(default=False)
    passive_income_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name