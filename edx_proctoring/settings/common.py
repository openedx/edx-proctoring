"Common Pluggable Django App settings"


def plugin_settings(settings):
    "Injects local settings into django settings"
    settings.PROCTORING_SETTINGS = {}
    settings.PROCTORING_BACKENDS = {
        'DEFAULT': 'null',
        'null': {},
    }
    proctoring_js = (
        [
            'proctoring/js/models/proctored_exam_allowance_model.js',
            'proctoring/js/models/proctored_exam_attempt_model.js',
            'proctoring/js/models/proctored_exam_model.js',
            'proctoring/js/collections/proctored_exam_allowance_collection.js',
            'proctoring/js/collections/proctored_exam_attempt_collection.js',
            'proctoring/js/collections/proctored_exam_collection.js',
            'proctoring/js/views/Backbone.ModalDialog.js',
            'proctoring/js/views/proctored_exam_add_allowance_view.js',
            'proctoring/js/views/proctored_exam_allowance_view.js',
            'proctoring/js/views/proctored_exam_attempt_view.js',
            'proctoring/js/views/proctored_exam_view.js',
            'proctoring/js/views/proctored_exam_instructor_launch.js',
            'proctoring/js/proctored_app.js',
            'proctoring/js/exam_action_handler.js'
        ]
    )
    settings.PIPELINE_JS['proctoring'] = {
        'source_filenames': proctoring_js,
        'output_filename': 'js/lms-proctoring.js',
    }
