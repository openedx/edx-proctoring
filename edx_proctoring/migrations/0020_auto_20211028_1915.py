# Generated by Django 2.2.24 on 2021-10-28 19:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0019_proctoredexamsoftwaresecurereview_encrypted_video_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proctoredexamsoftwaresecurereview',
            name='video_url',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='proctoredexamsoftwaresecurereviewhistory',
            name='video_url',
            field=models.TextField(null=True),
        ),
    ]
