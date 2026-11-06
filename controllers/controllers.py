# -*- coding: utf-8 -*-
# from odoo import http


# class HrSimplePayroll(http.Controller):
#     @http.route('/hr_simple_payroll/hr_simple_payroll', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hr_simple_payroll/hr_simple_payroll/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('hr_simple_payroll.listing', {
#             'root': '/hr_simple_payroll/hr_simple_payroll',
#             'objects': http.request.env['hr_simple_payroll.hr_simple_payroll'].search([]),
#         })

#     @http.route('/hr_simple_payroll/hr_simple_payroll/objects/<model("hr_simple_payroll.hr_simple_payroll"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hr_simple_payroll.object', {
#             'object': obj
#         })

