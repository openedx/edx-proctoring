# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # rename the table to be in the proctoring_* namespace
        db.rename_table('edx_proctoring_proctoredexamstudentattempthistory', 'proctoring_proctoredexamstudentattempthistory')

        # Adding field 'ProctoredExamStudentAttemptHistory.attempt_id'

        db.add_column('proctoring_proctoredexamstudentattempthistory', 'attempt_id',
                      self.gf('django.db.models.fields.IntegerField')(null=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'ProctoredExamStudentAttemptHistory.attempt_id'
        db.delete_column('proctoring_proctoredexamstudentattempthistory', 'attempt_id')

        # rename the table to be in the edx_proctoring_* namespace
        db.rename_table('proctoring_proctoredexamstudentattempthistory', 'edx_proctoring_proctoredexamstudentattempthistory')



    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'edx_proctoring.proctoredexam': {
            'Meta': {'unique_together': "(('course_id', 'content_id'),)", 'object_name': 'ProctoredExam', 'db_table': "'proctoring_proctoredexam'"},
            'content_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'course_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'exam_name': ('django.db.models.fields.TextField', [], {}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_practice_exam': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_proctored': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'time_limit_mins': ('django.db.models.fields.IntegerField', [], {})
        },
        'edx_proctoring.proctoredexamsoftwaresecurecomment': {
            'Meta': {'object_name': 'ProctoredExamSoftwareSecureComment', 'db_table': "'proctoring_proctoredexamstudentattemptcomment'"},
            'comment': ('django.db.models.fields.TextField', [], {}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'duration': ('django.db.models.fields.IntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'review': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExamSoftwareSecureReview']"}),
            'start_time': ('django.db.models.fields.IntegerField', [], {}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'stop_time': ('django.db.models.fields.IntegerField', [], {})
        },
        'edx_proctoring.proctoredexamsoftwaresecurereview': {
            'Meta': {'object_name': 'ProctoredExamSoftwareSecureReview', 'db_table': "'proctoring_proctoredexamsoftwaresecurereview'"},
            'attempt_code': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'raw_data': ('django.db.models.fields.TextField', [], {}),
            'review_status': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'video_url': ('django.db.models.fields.TextField', [], {})
        },
        'edx_proctoring.proctoredexamstudentallowance': {
            'Meta': {'unique_together': "(('user', 'proctored_exam', 'key'),)", 'object_name': 'ProctoredExamStudentAllowance', 'db_table': "'proctoring_proctoredexamstudentallowance'"},
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'edx_proctoring.proctoredexamstudentallowancehistory': {
            'Meta': {'object_name': 'ProctoredExamStudentAllowanceHistory', 'db_table': "'proctoring_proctoredexamstudentallowancehistory'"},
            'allowance_id': ('django.db.models.fields.IntegerField', [], {}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'edx_proctoring.proctoredexamstudentattempt': {
            'Meta': {'unique_together': "(('user', 'proctored_exam'),)", 'object_name': 'ProctoredExamStudentAttempt', 'db_table': "'proctoring_proctoredexamstudentattempt'"},
            'allowed_time_limit_mins': ('django.db.models.fields.IntegerField', [], {}),
            'attempt_code': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'completed_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_sample_attempt': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_poll_ipaddr': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'last_poll_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'started_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'student_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'taking_as_proctored': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'edx_proctoring.proctoredexamstudentattempthistory': {
            'Meta': {'object_name': 'ProctoredExamStudentAttemptHistory', 'db_table': "'proctoring_proctoredexamstudentattempthistory'"},
            'allowed_time_limit_mins': ('django.db.models.fields.IntegerField', [], {}),
            'attempt_code': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'attempt_id': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'completed_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_sample_attempt': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'started_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'student_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'taking_as_proctored': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        }
    }

    complete_apps = ['edx_proctoring']
