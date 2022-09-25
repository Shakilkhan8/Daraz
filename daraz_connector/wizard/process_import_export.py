from odoo import models, fields, api
from odoo.exceptions import Warning
from _collections import OrderedDict


class ImportExportProcess(models.TransientModel):
    _name = 'import.export.process'
    _description = "Import Export Process"
 
    is_import_order = fields.Boolean("Order Import ?", default=False, help="Import Remaining Orders.")
    is_import_category = fields.Boolean("Category Import ?", default=False, help="Import Categories.")
    is_import_attribute = fields.Boolean("Attribute Import ?", default=False, help="Import Attributes.")
    is_import_product = fields.Boolean("Product Import ?", default=False, help="Import Products.")
    instance_ids = fields.Many2many("daraz.connector", string="Stores")

    @api.onchange('is_import_order')
    def allusers(self):

        val = self.is_import_order
        if (val):
            user_ids = self.env['daraz.connector'].sudo().search([])
            for i in user_ids:
                daraz_id = self.env['res.partner'].sudo().search([("name",'=','Daraz')],limit=1)
                i.state='connected'
                i.import_pending_orders=True
                i.so_auto_import=True
                # i.write({'so_auto_import': True})
                # i.write({'import_pending_orders':True})
                i.default_customer_id=daraz_id.id
                i.write({'default_customer_id': daraz_id.id})
                # print(i.default_customer_id)

            self.instance_ids = user_ids
        else:
            self.instance_ids = []

    @api.model
    def default_get(self, fields):
        res = super(ImportExportProcess, self).default_get(fields)
        if 'default_instance_id' in self._context:
            res.update({'instance_ids': [(6, 0, [self._context.get('default_instance_id')])]})
        elif 'instance_ids' in fields:
            instances = self.env['daraz.connector'].search([('state', '=', 'confirm')])
            res.update({'instance_ids': [(6, 0, instances.ids)]})
        return res

    def import_sale_orders(self):
        so_obj = self.env['sale.order']

        Storeobj = self.env['daraz.connector'].search([('state', '=', 'connected')])

        # for instance in self.instance_ids:
        #     so_obj.import_orders(instance)
        #     print("Success")
        # return True

        for instance in Storeobj:
            so_obj.import_orders(instance)
        print("Success fully Create all Sale orders")
        return True

    
    def import_categories(self):
        category_obj = self.env["product.category"]
        for instance in self.instance_ids:
            category_obj.import_category(instance)

        return True

    def import_attribute(self):
        attribute_obj = self.env["product.attribute"]
        for instance in self.instance_ids:
            attribute_obj.import_attributes(instance)
            
        return True

    def import_product(self):
        product_obj = self.env["product.product"]
        for instance in self.instance_ids:
            product_obj.import_product(instance)
            
        return True
