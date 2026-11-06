# -*- coding: utf-8 -*-

from odoo import fields, models


class HrSimplePayslip(models.Model):
    _name = 'hr.simple.payslip'
    _description = 'Simple Payslip'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        default='New',
    )
    employee_name = fields.Char(string='Employee', required=True)
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done'),
        ],
        string='Status',
        default='draft',
        required=True,
    )
