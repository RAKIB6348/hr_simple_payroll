# -*- coding: utf-8 -*-

import calendar
from datetime import date

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


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
    employee_name = fields.Char(string='Employee')
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

    line_ids = fields.One2many(
        comodel_name='hr.simple.payslip.line',
        inverse_name='payslip_id',
        string='Employee Salary Lines',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    amount = fields.Monetary(
        string='Amount',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id',
    )
    total_wage = fields.Monetary(
        string='Total Wage',
        compute='_compute_total_wage',
        store=True,
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

    @api.depends('line_ids.wage')
    def _compute_total_wage(self):
        for payslip in self:
            payslip.total_wage = sum(payslip.line_ids.mapped('wage'))

    @api.depends('total_wage')
    def _compute_amount(self):
        for payslip in self:
            payslip.amount = payslip.total_wage

    def _get_applicable_contract(self, employee):
        """Return the contract applicable to this payslip's period.

        A contract is applicable when it is running/closed (not draft or
        cancelled) and its date range overlaps the payroll period. When
        several match, the most recently started one wins.
        """
        self.ensure_one()
        contracts = employee.contract_ids.filtered(
            lambda contract: contract.state in ('open', 'close')
            and (not contract.date_start or contract.date_start <= self.date_to)
            and (not contract.date_end or contract.date_end >= self.date_from)
        )
        return contracts.sorted(
            key=lambda contract: (contract.date_start or date.min, contract.id),
            reverse=True,
        )[:1]

    def action_generate_employees(self):
        """Populate salary lines from employees' applicable contracts."""
        self.ensure_one()

        if not self.id:
            raise UserError(_(
                'Please save the payslip before generating employees.'
            ))
        if self.state != 'draft':
            raise UserError(_(
                'Employees can only be generated for a payslip in Draft state.'
            ))
        if not self.date_from or not self.date_to:
            raise UserError(_(
                'Please select a payroll period (Month and Year) first.'
            ))
        if self.date_from > self.date_to:
            raise UserError(_(
                'Date From must be earlier than or equal to Date To.'
            ))

        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('company_id', 'in', self.env.companies.ids),
        ], order='name')

        existing_employee_ids = set(self.line_ids.employee_id.ids)
        commands = []
        skipped = self.env['hr.employee']

        for employee in employees:
            if employee.id in existing_employee_ids:
                continue
            contract = self._get_applicable_contract(employee)
            if not contract:
                skipped |= employee
                continue
            commands.append(Command.create({
                'employee_id': employee.id,
                'wage': contract.wage,
            }))
            existing_employee_ids.add(employee.id)

        if commands:
            self.write({'line_ids': commands})

        if skipped:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Employees skipped'),
                    'message': _(
                        'No applicable contract was found for: %s',
                        ', '.join(skipped.mapped('name')),
                    ),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        if not commands:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No changes'),
                    'message': _('No new employees were added.'),
                    'type': 'info',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Employees generated'),
                'message': _('%s employee(s) added.', len(commands)),
                'type': 'success',
                'sticky': False,
            },
        }


class HrSimplePayslipLine(models.Model):
    _name = 'hr.simple.payslip.line'
    _description = 'Payslip Employee Salary Line'
    _order = 'id'

    payslip_id = fields.Many2one(
        comodel_name='hr.simple.payslip',
        string='Payslip',
        required=True,
        ondelete='cascade',
        index=True,
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        ondelete='restrict',
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='payslip_id.currency_id',
        readonly=True,
    )
    wage = fields.Monetary(
        string='Wage',
        required=True,
        currency_field='currency_id',
    )

    _sql_constraints = [
        (
            'payslip_employee_uniq',
            'unique(payslip_id, employee_id)',
            'An employee can only be added once per payslip.',
        ),
    ]
