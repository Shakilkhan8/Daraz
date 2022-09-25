# -*- coding: utf-8 -*-
{
    'name': "Daraz Connector",

    'summary': """
        Daraz Api connector that integrate the inventory and sale orders
        Module can sync date between odoo and Daraz Store""",

    'description': """
        Daraz Connector
    """,

    'author': "Hunain Ak",
    'website': "http://www.hunainahmed.com",

    
    'category': 'Tools',
    'version': '1.0',

    'depends': ['sale_stock','sale_management'],

    'data': [
        'security/ir.model.access.csv',
        'views/daraz_instance.xml',
        'views/sale.xml',
        'views/ir_cron.xml',
        'views/view_process_job.xml',
        'wizard/process_import_export_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,

    'images': ['static/description/main_screen.jpg'],
    # 'demo': [
    #     'demo/demo.xml',
    # ],
}
