from __future__ import annotations

from frappe import _


def get_data():
    return [
        {
            "module_name": "OCEN Connector",
            "color": "blue",
            "icon": "octicon octicon-plug",
            "type": "module",
            "label": _("OCEN Connector"),
        }
    ]
