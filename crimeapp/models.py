from django.db import models

class SavedRoute(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_lat = models.FloatField()
    start_lon = models.FloatField()
    end_lat = models.FloatField()
    end_lon = models.FloatField()

    def __str__(self):
        return self.name
