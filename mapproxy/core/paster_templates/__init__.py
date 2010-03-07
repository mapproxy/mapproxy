from paste.util.template import paste_script_template_renderer
from paste.script.templates import Template, var


class ConfigurationTemplate(Template):
    _template_dir = 'templates'
    summary = "MapProxy configuration template"
    vars = [
        # var('varname', 'help text', default='value'),
    ]

    template_renderer = staticmethod(paste_script_template_renderer)
