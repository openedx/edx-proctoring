# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'ProctoredExamStudentAttempt.student_name'
        db.add_column('proctoring_proctoredexamstudentattempt', 'student_name',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'ProctoredExamStudentAttempt.student_name'
        db.delete_column('proctoring_proctoredexamstudentattempt', 'student_name')


    models = {
        'edx_proctoring.proctoredexam': {
            'Meta': {'unique_together': "(('course_id', 'content_id'),)", 'object_name': 'ProctoredExam', 'db_table': "'proctoring_proctoredexam'"},
            'content_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'course_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'exam_name': ('django.db.models.fields.TextField', [], {}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_proctored': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'time_limit_mins': ('django.db.models.fields.IntegerField', [], {})
        },
        'edx_proctoring.proctoredexamstudentallowance': {
            'Meta': {'unique_together': "(('user_id', 'proctored_exam', 'key'),)", 'object_name': 'ProctoredExamStudentAllowance', 'db_table': "'proctoring_proctoredexamstudentallowance'"},
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'user_id': ('django.db.models.fields.IntegerField', [], {}),
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
            'user_id': ('django.db.models.fields.IntegerField', [], {}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'edx_proctoring.proctoredexamstudentattempt': {
            'Meta': {'object_name': 'ProctoredExamStudentAttempt', 'db_table': "'proctoring_proctoredexamstudentattempt'"},
            'completed_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'started_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'student_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'taking_as_proctored': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['edx_proctoring']