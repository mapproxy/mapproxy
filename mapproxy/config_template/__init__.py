try:
    from paste.util.template import paste_script_template_renderer
    from paste.script.templates import Template #, var

    class PasterConfigurationTemplate(Template):
        _template_dir = 'paster'
        summary = "MapProxy configuration template"
        vars = [
            # var('varname', 'help text', default='value'),
        ]

        template_renderer = staticmethod(paste_script_template_renderer)
except ImportError:
    pass