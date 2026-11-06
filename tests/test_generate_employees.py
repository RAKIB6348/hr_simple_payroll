# -*- coding: utf-8 -*-

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGenerateEmployees(TransactionCase):
    """Tests for the Generate Employees action on hr.simple.payslip."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Use a dedicated company so the employee search cannot pick up
        # records created by other modules or demo data.
        cls.company = cls.env['res.company'].create({
            'name': 'Simple Payroll Test Company',
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))

        cls.employee_a = cls.env['hr.employee'].create({
            'name': 'Employee A',
            'company_id': cls.company.id,
        })
        cls.employee_b = cls.env['hr.employee'].create({
            'name': 'Employee B',
            'company_id': cls.company.id,
        })
        cls.employee_no_contract = cls.env['hr.employee'].create({
            'name': 'Employee Without Contract',
            'company_id': cls.company.id,
        })

        cls.contract_a = cls._create_contract(
            cls.employee_a, 3000.0, date(2026, 1, 1),
        )
        cls.contract_b = cls._create_contract(
            cls.employee_b, 2500.0, date(2026, 1, 1),
        )

    @classmethod
    def _create_contract(cls, employee, wage, date_start,
                         date_end=None, state='open'):
        vals = {
            'name': 'Contract for %s' % employee.name,
            'employee_id': employee.id,
            'wage': wage,
            'date_start': date_start,
            'state': state,
        }
        if date_end:
            vals['date_end'] = date_end
        return cls.env['hr.contract'].create(vals)

    def _create_payslip(self, **vals):
        values = {
            'employee_name': 'Payroll Test',
            'month': '11',
            'year': 2026,
        }
        values.update(vals)
        return self.env['hr.simple.payslip'].create(values)

    def test_generate_employees_applies_period_and_wages(self):
        payslip = self._create_payslip()

        self.assertEqual(payslip.date_from, date(2026, 11, 1))
        self.assertEqual(payslip.date_to, date(2026, 11, 30))

        payslip.action_generate_employees()

        self.assertEqual(len(payslip.line_ids), 2)
        lines = {line.employee_id: line for line in payslip.line_ids}
        self.assertIn(self.employee_a, lines)
        self.assertIn(self.employee_b, lines)
        self.assertAlmostEqual(lines[self.employee_a].wage, 3000.0)
        self.assertAlmostEqual(lines[self.employee_b].wage, 2500.0)
        self.assertAlmostEqual(payslip.total_wage, 5500.0)

    def test_generate_twice_does_not_duplicate(self):
        payslip = self._create_payslip()

        payslip.action_generate_employees()
        payslip.action_generate_employees()

        self.assertEqual(len(payslip.line_ids), 2)
        self.assertEqual(
            len(set(payslip.line_ids.mapped('employee_id').ids)), 2,
        )
        self.assertEqual(
            len(payslip.line_ids.filtered(
                lambda line: line.employee_id == self.employee_a,
            )),
            1,
        )

    def test_employee_without_contract_is_skipped(self):
        payslip = self._create_payslip()

        result = payslip.action_generate_employees()

        self.assertNotIn(self.employee_no_contract, payslip.line_ids.employee_id)
        self.assertEqual(len(payslip.line_ids), 2)
        self.assertTrue(
            all(line.wage for line in payslip.line_ids),
            'Skipped employees must not create zero-wage lines.',
        )
        self.assertEqual(result.get('tag'), 'display_notification')
        self.assertEqual(result['params']['type'], 'warning')

    def test_total_wage_is_computed_from_lines(self):
        payslip = self._create_payslip()
        payslip.action_generate_employees()

        self.assertAlmostEqual(payslip.total_wage, 5500.0)

        line_a = payslip.line_ids.filtered(
            lambda line: line.employee_id == self.employee_a,
        )
        line_a.wage = 4000.0

        self.assertAlmostEqual(payslip.total_wage, 6500.0)

    def test_generate_only_in_draft(self):
        payslip = self._create_payslip(state='done')

        with self.assertRaises(UserError):
            payslip.action_generate_employees()

        self.assertFalse(payslip.line_ids)

    def test_contract_outside_period_is_ignored(self):
        employee = self.env['hr.employee'].create({
            'name': 'Employee Old Contract',
            'company_id': self.company.id,
        })
        self._create_contract(
            employee,
            9999.0,
            date(2026, 1, 1),
            date(2026, 10, 31),
            state='close',
        )

        payslip = self._create_payslip()
        payslip.action_generate_employees()

        self.assertNotIn(employee, payslip.line_ids.employee_id)
        self.assertEqual(len(payslip.line_ids), 2)

    def test_future_contract_is_ignored(self):
        employee = self.env['hr.employee'].create({
            'name': 'Employee Future Contract',
            'company_id': self.company.id,
        })
        self._create_contract(
            employee,
            9999.0,
            date(2026, 12, 1),
        )

        payslip = self._create_payslip()
        payslip.action_generate_employees()

        self.assertNotIn(employee, payslip.line_ids.employee_id)
        self.assertEqual(len(payslip.line_ids), 2)

    def test_generate_requires_saved_payslip(self):
        payslip = self.env['hr.simple.payslip'].new({
            'employee_name': 'Unsaved Payslip',
            'month': '11',
            'year': 2026,
        })

        with self.assertRaises(UserError):
            payslip.action_generate_employees()
