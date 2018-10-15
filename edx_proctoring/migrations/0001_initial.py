# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
from django.conf import settings
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProctoredExam',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('course_id', models.CharField(max_length=255, db_index=True)),
                ('content_id', models.CharField(max_length=255, db_index=True)),
                ('external_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('exam_name', models.TextField()),
                ('time_limit_mins', models.IntegerField()),
                ('due_date', models.DateTimeField(null=True)),
                ('is_proctored', models.BooleanField(default=False)),
                ('is_practice_exam', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'proctoring_proctoredexam',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamReviewPolicy',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('review_policy', models.TextField()),
                ('proctored_exam', models.ForeignKey(to='edx_proctoring.ProctoredExam', on_delete=models.CASCADE)),
                ('set_by_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamreviewpolicy',
                'verbose_name': 'Proctored exam review policy',
                'verbose_name_plural': 'Proctored exam review policies',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamReviewPolicyHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('original_id', models.IntegerField(db_index=True)),
                ('review_policy', models.TextField()),
                ('proctored_exam', models.ForeignKey(to='edx_proctoring.ProctoredExam', on_delete=models.CASCADE)),
                ('set_by_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamreviewpolicyhistory',
                'verbose_name': 'proctored exam review policy history',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamSoftwareSecureComment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('start_time', models.IntegerField()),
                ('stop_time', models.IntegerField()),
                ('duration', models.IntegerField()),
                ('comment', models.TextField()),
                ('status', models.CharField(max_length=255)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamstudentattemptcomment',
                'verbose_name': 'proctored exam software secure comment',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamSoftwareSecureReview',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('attempt_code', models.CharField(max_length=255, db_index=True)),
                ('review_status', models.CharField(max_length=255)),
                ('raw_data', models.TextField()),
                ('video_url', models.TextField()),
                ('exam', models.ForeignKey(to='edx_proctoring.ProctoredExam', null=True, on_delete=models.CASCADE)),
                ('reviewed_by', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)),
                ('student', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamsoftwaresecurereview',
                'verbose_name': 'Proctored exam software secure review',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamSoftwareSecureReviewHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('attempt_code', models.CharField(max_length=255, db_index=True)),
                ('review_status', models.CharField(max_length=255)),
                ('raw_data', models.TextField()),
                ('video_url', models.TextField()),
                ('exam', models.ForeignKey(to='edx_proctoring.ProctoredExam', null=True, on_delete=models.CASCADE)),
                ('reviewed_by', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)),
                ('student', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamsoftwaresecurereviewhistory',
                'verbose_name': 'Proctored exam review archive',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamStudentAllowance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('key', models.CharField(max_length=255)),
                ('value', models.CharField(max_length=255)),
                ('proctored_exam', models.ForeignKey(to='edx_proctoring.ProctoredExam', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamstudentallowance',
                'verbose_name': 'proctored allowance',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamStudentAllowanceHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('allowance_id', models.IntegerField()),
                ('key', models.CharField(max_length=255)),
                ('value', models.CharField(max_length=255)),
                ('proctored_exam', models.ForeignKey(to='edx_proctoring.ProctoredExam', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamstudentallowancehistory',
                'verbose_name': 'proctored allowance history',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamStudentAttempt',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('started_at', models.DateTimeField(null=True)),
                ('completed_at', models.DateTimeField(null=True)),
                ('last_poll_timestamp', models.DateTimeField(null=True)),
                ('last_poll_ipaddr', models.CharField(max_length=32, null=True)),
                ('attempt_code', models.CharField(max_length=255, null=True, db_index=True)),
                ('external_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('allowed_time_limit_mins', models.IntegerField()),
                ('status', models.CharField(max_length=64)),
                ('taking_as_proctored', models.BooleanField(default=False)),
                ('is_sample_attempt', models.BooleanField(default=False)),
                ('student_name', models.CharField(max_length=255)),
                ('review_policy_id', models.IntegerField(null=True)),
                ('proctored_exam', models.ForeignKey(to='edx_proctoring.ProctoredExam', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamstudentattempt',
                'verbose_name': 'proctored exam attempt',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamStudentAttemptHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('attempt_id', models.IntegerField(null=True)),
                ('started_at', models.DateTimeField(null=True)),
                ('completed_at', models.DateTimeField(null=True)),
                ('attempt_code', models.CharField(max_length=255, null=True, db_index=True)),
                ('external_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('allowed_time_limit_mins', models.IntegerField()),
                ('status', models.CharField(max_length=64)),
                ('taking_as_proctored', models.BooleanField(default=False)),
                ('is_sample_attempt', models.BooleanField(default=False)),
                ('student_name', models.CharField(max_length=255)),
                ('review_policy_id', models.IntegerField(null=True)),
                ('last_poll_timestamp', models.DateTimeField(null=True)),
                ('last_poll_ipaddr', models.CharField(max_length=32, null=True)),
                ('proctored_exam', models.ForeignKey(to='edx_proctoring.ProctoredExam', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamstudentattempthistory',
                'verbose_name': 'proctored exam attempt history',
            },
        ),
        migrations.AddField(
            model_name='proctoredexamsoftwaresecurecomment',
            name='review',
            field=models.ForeignKey(to='edx_proctoring.ProctoredExamSoftwareSecureReview', on_delete=models.CASCADE),
        ),
        migrations.AlterUniqueTogether(
            name='proctoredexam',
            unique_together=set([('course_id', 'content_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='proctoredexamstudentattempt',
            unique_together=set([('user', 'proctored_exam')]),
        ),
        migrations.AlterUniqueTogether(
            name='proctoredexamstudentallowance',
            unique_together=set([('user', 'proctored_exam', 'key')]),
        ),
    ]
