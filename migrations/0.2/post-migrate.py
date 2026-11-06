# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Backfill Amount for payslips created before it became computed."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    payslips = env['hr.simple.payslip'].search([])
    if not payslips:
        return

    field = env['hr.simple.payslip']._fields['amount']
    env.add_to_compute(field, payslips)
    env['hr.simple.payslip'].flush_model(['amount'])
