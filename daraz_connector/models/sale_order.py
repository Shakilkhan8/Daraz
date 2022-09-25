from odoo import models, fields, api,_
from odoo.exceptions import Warning
from datetime import datetime ,timezone
import requests
import urllib.parse
from hashlib import sha256
from hmac import HMAC
import json


class SaleOrder(models.Model):
    _inherit = "sale.order"

    instance_id = fields.Many2one('daraz.connector', 'Daraz Store')
    update_order_status = fields.Boolean('Update Status to Daraz', help='Want to update Order status to daraz?')
    orderid = fields.Char("Daraz Order Reference", help="Daraz Order Reference")
    order_status = fields.Selection([('pending','Pending'), 
                                     ('ready_to_ship','Ready To Ship'), 
                                     ('delivered','Delivered'), ('canceled','Cancelled'),
                                     ('shipped','Shipped'),  ('returned','Returned'),
                                     ('return_waiting_for_approval','Return Waiting For Approval'), 
                                     ('return_shipped_by_customer','Return Shipped By Customer'), 
                                     ('return_rejected','Return Rejected'),
                                     ('processing','Processing'), 
                                     ('failed','Failed')
                                    ],string="Daraz Order Status", track_visibility='onchange', copy=False)
    # tracking_no = fields.Integer("Tracking No")
    customer_name = fields.Char("Customer Name")
    address_name = fields.Text("Address")
    phone_no = fields.Char("Phone")
    city_id = fields.Char("City")
    status_id = fields.Char("Status")
    delivery_type = fields.Selection([('dropship','Dropship'),('pickup','Pickup'),('send_to_warehouse','Send to Warehouse')],"Delivery Type", default='dropship')
    # mobile_no = fields.Char("Mobile No")




    def onchange_delivery_type(self):
        if self.delivery_type  !='dropship':
            raise Warning ('Currently Daraz is only support Dropship')

    def connect_with_store(self, action=None, req=None, instance_id=False, extra_parameters={}):
        darazStore = instance_id
        url = darazStore.api_url
        key = darazStore.api_key
        format = "json"
        userId = darazStore.userId
        method = req if req else 'GET'

        now = datetime.now().timestamp()
        test = datetime.fromtimestamp(now, tz=timezone.utc).replace(microsecond=0).isoformat()
        parameters = {
            'UserID': userId,
            'Version': "1.0",
            'Action': action,
            'Format': format,
            'Timestamp': test}

        if extra_parameters:
            parameters.update(extra_parameters)
        concatenated = urllib.parse.urlencode(sorted(parameters.items()))
        data = concatenated.encode('utf-8')
        parameters['Signature'] = HMAC(key.encode('utf-8'), data,
                                       sha256).hexdigest()

        headers = {
            'Content-Type': "application/json",
            'Accept': "*/*",
            'Connection': "keep-alive",
            'cache-control': "no-cache"
        }
        try:
            response = requests.request(method, url, headers=headers, params=parameters)
        except Exception as e:
            raise Warning(_(response.text))

        return json.loads(response.text)


    def import_orders(self, instance, job=False):
        flag = 0
        count=0
        # print("Schedulers",instance.name)
        if instance.import_pending_orders:
            res = self.connect_with_store('GetOrders', 'GET', instance_id=instance, extra_parameters={'Status':'pending'})
            print("res2",res)
            result = res.get('SuccessResponse', {}).get('Body', {})
            # print("result",result)
        else:
            res = self.connect_with_store('GetOrders', 'GET', instance_id=instance)
            result = res.get('SuccessResponse', {}).get('Body', {})
            # print("res3",res)
        if job:
            job.response = res


        if result:
            for val in result.get('Orders'):
                # status = val.get('Statuses', '') and val.get('Statuses', '')[0]
                # if instance.import_pending_orders and status != 'pending':
                #     continue
                # print(val)
                orderid = val.get('OrderId')
                if self.search([('instance_id', '=', instance.id), ('orderid', '=', orderid)]):
                    continue
                status = val.get('Statuses','')
                # print(type(status))
                # print(status)

                items_count = val.get('ItemsCount')
                res = self.connect_with_store('GetOrderItems', 'GET', instance_id=instance, extra_parameters={'OrderId': orderid})

                if result:
                    if 'pending' in status :


                        if flag > 1:
                            flag=0
                            self._cr.commit()
                        create_date = val.get('CreatedAt')
                        update_date = val.get('UpdatedAt')
                        address = val.get('AddressShipping').get('Address1')
                        phone = val.get('AddressShipping').get('Phone')
                        city = val.get('AddressShipping').get('City')
                        # status_id = val.get('AddressShipping').get('Statuses')
                        # print("status",status)
                        # print(address)
                        # print(phone)
                        # print(city)
                        first_name = val.get('CustomerFirstName', '')
                        last_name = val.get('CustomerLastName', '')
                        cust_name = "%s %s" % (first_name, last_name)
                        print(cust_name)
                        print("status", status)
                        order = self.create({
                                'partner_id': instance.default_customer_id.id,
                                'date_order': create_date,
                                'address_name':address ,
                                'phone_no':phone,
                                'city_id':city ,
                                'status_id': "Pending",
                                'orderid' : orderid,
                                'customer_name': cust_name,
                                'order_status': status and status[0],
                                'instance_id' : instance.id,
                            })
                        # print(order)
                        flag=flag+1
                        self.create_order_line(res.get('SuccessResponse', {}).get('Body', {}), items_count, order, instance)

        else:
            if job:
                job.env['process.job.line'].create({'job_id': job.id, 'message': "Empty Response"})

        return True

    @api.model
    def search_product(self, sku='', instance=False):
        product_obj = self.env['product.product']       
        product = product_obj.search(
            [('instance_id', '=', instance.id), ('default_code', '=', sku)], limit=1)
        if product:
            return product
        odoo_product = sku and product_obj.search([('default_code', '=', sku)], limit=1)
        if odoo_product:
            return odoo_product
        return False

    @api.model
    def create_product(self, name='', sku='', instance=False):
        product = self.env['product.product'].create({
            'name': name, 'default_code': sku, 'sku': sku, 'instance_id': instance.id,
        })
        return product

    @api.model
    def create_order_line(self, records, qty=0.00, order=False, instance=False):
        for record in records.get('OrderItems', {}):
            item_id = record.get('OrderItemId')
            sku = record.get('Sku').replace(' ', '')
            name = record.get('Name', '')
            shop_sku = record.get('ShopSku')
            # res = self.connect_with_store('GetProducts', 'GET', instance_id=instance, extra_parameters={'search':sku})
            # result = res.get('SuccessResponse', {}).get('Body', {})
            # result.get('Products')
            
            product = self.search_product(sku, instance)
            if not product:
                product = self.create_product(name, sku, instance)
            price_unit = record.get('ItemPrice')

            line_extra_vals = {
                'item_id': item_id,
                'shop_id': record.get('ShopId'),
                'sku': sku,
                'shop_sku': shop_sku,
                'name': name,
                'shipping_type': record.get('ShippingType'),
                'price_unit': record.get('ItemPrice'),
                'paid_price': record.get('PaidPrice'),
                # 'currency': record.get('Currency'),
                'tax_amount': record.get('TaxAmount'),
                'shipping_amount': record.get('ShippingAmount'),
                'shipping_service_cost': record.get('ShippingServiceCost'),
                'voucher_amount': record.get('VoucherAmount'),
                'voucher_code': record.get('VoucherCode'),
                'daraz_status': record.get('Status'),
                'shipment_provider': record.get('ShipmentProvider'),
                'delivery': record.get('Delivery'),
                'is_digital': record.get('IsDigital'),
                'digital_delivery_info': record.get('DigitalDeliveryInfo'),
                'tracking_code': record.get('TrackingCode'),
                'tracking_code_pre': record.get('TrackingCodePre'),
                'reason': record.get('Reason'),
                'reason_detail': record.get('ReasonDetail'),
                'purchase_order_id': record.get('PurchaseOrderId'),
                'purchase_order_no': record.get('PurchaseOrderNumber'),
                'package_id': record.get('PackageId'),
                'promised_shipping_time': record.get('PromisedShippingTime'),
                'extra_attributes': record.get('ExtraAttributes'),
                'shipping_provider_type': record.get('ShippingProviderType'),
                'create_date': record.get('CreatedAt'),
                'update_date': record.get('UpdatedAt'),
                'return_status': record.get('ReturnStatus'),
                'product_main_image': record.get('productMainImage'),
                'variation': record.get('Variation'),
                'color_family': record.get('Color Family'),
                'product_detail_url': record.get('ProductDetailUrl'),
                'invoice_number': record.get('invoiceNumber')}

            line = self.create_sale_order_line(product, qty, name, order, price_unit)
            line.write({

            })

    @api.model
    def create_sale_order_line(self, product, quantity,  name, order, price):

        sale_order_line_obj = self.env['sale.order.line']
        uom_id = product and product.uom_id and product.uom_id.id or False
        product_data = {
            'product_id': product and product.ids[0] or False,
            'order_id': order.id,
            'company_id': order.company_id.id,
            'product_uom': uom_id,
            'name': name,
            'display_type': False,
        }
        tmp_sale_line = sale_order_line_obj.new(product_data)
        tmp_sale_line.product_id_change()
        so_line_vals = sale_order_line_obj._convert_to_write(
            {name: tmp_sale_line[name] for name in tmp_sale_line._cache})
        
        so_line_vals.update(
            {
                'order_id': order.id,
                'product_uom_qty': quantity,
                'price_unit': price,
            }
        )
        line = sale_order_line_obj.create(so_line_vals)
        return line

    
    @api.model
    def auto_import_sale_order(self, ctx={}):
        instance_obj = self.env["daraz.connector"]
        if not isinstance(ctx, dict) or not 'instance_id' in ctx:
            return True
        instance_id = ctx.get('instance_id', False)
        instance = instance_id and instance_obj.search(
            [('id', '=', instance_id), ('state', '=', 'connected')]) or False
        if instance:
            job = self.env['process.job'].create(
            {'instance_id': instance.id, 'process_type': 'order', 'operation_type': 'import',
             'message': 'Process for Import Order'})

            self.import_orders(instance, job)
            instance.so_import_next_execution = instance.so_import_cron_id.nextcall
        return True

    @api.model
    def auto_import_update_sale_status(self, ctx={}):
        instance_obj = self.env["daraz.connector"]
        if not isinstance(ctx, dict) or not 'instance_id' in ctx:
            return True
        instance_id = ctx.get('instance_id', False)
        instance = instance_id and instance_obj.search(
            [('id', '=', instance_id), ('state', '=', 'connected')]) or False
        if instance:
            job = self.env['process.job'].create(
            {'instance_id': instance.id, 'process_type': 'order', 'operation_type': 'import',
             'message': 'Process for import Order status'})
            orders = self.env['sale.order'].search([('instance_id','=',instance.id)])
            for order in orders:
                res = self.connect_with_store('GetOrder', 'GET', instance_id=instance, extra_parameters={'orderid':order.orderid})
                result = res.get('SuccessResponse', {}).get('Body', {})
                status = res.get('Statuses','')
                order.order_status = status and status[0]
            instance.so_import_next_execution = instance.so_import_cron_id.nextcall
        return True

    @api.model
    def auto_export_update_sale_status(self, ctx={}):
        instance_obj = self.env["daraz.connector"]
        if not isinstance(ctx, dict) or not 'instance_id' in ctx:
            return True
        instance_id = ctx.get('instance_id', False)
        instance = instance_id and instance_obj.search(
            [('id', '=', instance_id), ('state', '=', 'connected')]) or False
        if instance:
            job = self.env['process.job'].create(
            {'instance_id': instance.id, 'process_type': 'order', 'operation_type': 'export',
             'message': 'Process for export Order status'})
            orders = self.env['sale.order'].search([('instance_id','=',instance.id)])
            for order in orders:
                order.order_line.mapped('item_id')
            # self.update_orders(instance, job)
            # res = self.connect_with_store('SetStatusToReadyToShip', 'SET', instance_id=instance)
            # result = res.get('SuccessResponse', {}).get('Body', {})
            instance.so_import_next_execution = instance.so_import_cron_id.nextcall
        return True

    def action_ready_to_ship(self):
        for order in self:
            order.order_status = 'ready_to_ship'
        return True

    def action_delivered(self):
        for order in self:
            order.order_status = 'delivered'
        return True

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    item_id = fields.Char('Order ItemId')
    shop_id = fields.Char('Shop Id')
    sku = fields.Char('Sku')
    shop_sku = fields.Char('Shop Sku')
    shipping_type = fields.Char('Shipping Type')
    paid_price = fields.Float('Paid Price')
    currency_id = fields.Many2one('res.currency', 'Currency')
    tax_amount = fields.Char('Tax Amount')
    shipping_amount = fields.Char('Shipping Amount')
    shipping_service_cost = fields.Char('Shipping Service Cost')
    voucher_amount = fields.Char('Voucher Amount')
    voucher_code = fields.Char('Voucher Code')
    daraz_status = fields.Char('Status')
    shipment_provider = fields.Char('Shipment Provider')
    delivery = fields.Char('Delivery')
    is_digital = fields.Char('Is Digital')
    digital_delivery_info = fields.Char('Digital Delivery Info')
    tracking_code = fields.Char('Tracking Code')
    tracking_code_pre = fields.Char('Tracking Code Pre')
    reason = fields.Char('Reason')
    reason_detail = fields.Char('Reason Detail')
    purchase_order_id = fields.Char('Purchase OrderId')
    purchase_order_no = fields.Char('Purchase Order Number')
    package_id = fields.Char('PackageId')
    promised_shipping_time = fields.Char('Promised Shipping Time')
    extra_attributes = fields.Char('Extra Attributes')
    shipping_provider_type = fields.Char('Shipping Provider Type')
    create_date = fields.Char('Created At')
    update_date = fields.Char('Updated At')
    return_status = fields.Char('Return Status')
    product_main_image = fields.Char('Product Main Image')
    variation = fields.Char('Variation')
    color_family = fields.Char('Color Family')
    product_detail_url = fields.Char('Product Detail Url')
    invoice_number = fields.Char('Invoice Number')

    # _sql_constraints = [
    #     ('code_sku_uniq', 'unique (code,sku)', 'The Sku of the account must be unique per company !')
    # ]
