# Generated by Django 3.2.7 on 2021-09-30 19:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0018_historicalproctoredexamstudentattempt'),
    ]

    operations = [
        migrations.AddField(
            model_name='proctoredexamsoftwaresecurereview',
            name='encrypted_video_url',
            field=models.BinaryField(null=True),
        ),
    ]
