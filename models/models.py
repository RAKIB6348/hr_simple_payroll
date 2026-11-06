# -*- coding: utf-8 -*-

import calendar
from datetime import date

from odoo import api, fields, models


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

    # Payroll period selection
    month = fields.Selection(
        selection=[
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
        ],
        string='Month',
        default=lambda self: str(fields.Date.context_today(self).month),
    )
    year = fields.Integer(
        string='Year',
        default=lambda self: fields.Date.context_today(self).year,
    )
    date_from = fields.Date(
        string='Date From',
        default=lambda self: self._default_period_dates()[0],
        help='First day of the payroll period.',
    )
    date_to = fields.Date(
        string='Date To',
        default=lambda self: self._default_period_dates()[1],
        help='Last day of the payroll period.',
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

    @api.model
    def _get_period_dates(self, month, year):
        """Return (first_day, last_day) for the given month/year.

        Falls back to the current month/year when a value is missing or
        invalid. ``calendar.monthrange`` handles month length correctly,
        including leap years.
        """
        today = fields.Date.context_today(self)
        try:
            month = int(month) if month else today.month
            year = int(year) if year else today.year
        except (TypeError, ValueError):
            month, year = today.month, today.year

        if not 1 <= month <= 12:
            month, year = today.month, today.year

        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    @api.model
    def _default_period_dates(self):
        today = fields.Date.context_today(self)
        return self._get_period_dates(today.month, today.year)

    @api.onchange('month', 'year')
    def _onchange_month_year(self):
        if self.month and self.year:
            self.date_from, self.date_to = self._get_period_dates(
                self.month, self.year,
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Apply the selected period on programmatic creation.

        Only missing/empty dates are filled, so explicitly provided valid
        ``date_from``/``date_to`` values are preserved.
        """
        for vals in vals_list:
            if not vals.get('date_from') or not vals.get('date_to'):
                date_from, date_to = self._get_period_dates(
                    vals.get('month'), vals.get('year'),
                )
                if not vals.get('date_from'):
                    vals['date_from'] = date_from
                if not vals.get('date_to'):
                    vals['date_to'] = date_to
        return super().create(vals_list)
