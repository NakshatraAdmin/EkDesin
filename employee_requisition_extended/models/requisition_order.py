# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RequisitionOrderExtended(models.Model):
    """Extended Requisition Order with updated labels and vendor readonly logic"""
    _inherit = 'requisition.order'

    # Add related field for request_type from parent
    request_type = fields.Selection(
        related='requisition_product_id.request_type',
        string='Request Type',
        store=True,
        readonly=True
    )

    # Update requisition_type field: change label to "Request Type" and update selection labels
    requisition_type = fields.Selection(
        string='Request Type',
        selection=[
            ('purchase_order', 'Purchase Requisition'),
            ('internal_transfer', 'Material Requisition'),
        ],
        help='Type of requisition',
        required=True,
        default='purchase_order'
    )

    @api.model
    def default_get(self, fields_list):
        """Set default requisition_type based on parent request_type"""
        res = super(RequisitionOrderExtended, self).default_get(fields_list)
        
        # Get parent request_type from context or active_id
        parent_id = self.env.context.get('default_requisition_product_id') or self.env.context.get('active_id')
        if parent_id:
            parent = self.env['employee.purchase.requisition'].browse(parent_id)
            if parent.exists() and parent.request_type:
                if parent.request_type == 'material_requisition':
                    res['requisition_type'] = 'internal_transfer'
                elif parent.request_type == 'purchase_requisition':
                    res['requisition_type'] = 'purchase_order'
        
        return res

    @api.model
    def create(self, vals):
        """Set requisition_type based on parent request_type when creating and validate quantity and vendor selection"""
        # Validate quantity before creation
        if 'quantity' in vals and vals.get('quantity', 0) <= 0:
            raise ValidationError('Quantity must be greater than 0. Please enter a valid quantity.')
        
        # Validate vendor selection: Vendor can only be set after approval
        if 'partner_id' in vals and vals.get('partner_id'):
            if 'requisition_product_id' in vals:
                parent = self.env['employee.purchase.requisition'].browse(vals['requisition_product_id'])
                if parent.exists() and parent.request_type == 'purchase_requisition':
                    if parent.state not in ['approved']:
                        raise ValidationError(
                            'Vendor can only be selected after the requisition is approved. '
                            'Please wait for approval before selecting a vendor.'
                        )
                    # Only Purchase department users can set vendor
                    if not (self.env.user.has_group('purchase.group_purchase_user') or 
                            self.env.user.has_group('purchase.group_purchase_manager')):
                        raise ValidationError(
                            'Only Purchase department users can select vendors. '
                            'Please contact the Purchase department to assign a vendor.'
                        )
        
        if 'requisition_product_id' in vals and 'requisition_type' not in vals:
            parent = self.env['employee.purchase.requisition'].browse(vals['requisition_product_id'])
            if parent.request_type == 'material_requisition':
                vals['requisition_type'] = 'internal_transfer'
            elif parent.request_type == 'purchase_requisition':
                vals['requisition_type'] = 'purchase_order'
        elif 'requisition_product_id' in vals and 'requisition_type' in vals:
            # Ensure requisition_type matches parent request_type
            parent = self.env['employee.purchase.requisition'].browse(vals['requisition_product_id'])
            if parent.request_type == 'material_requisition' and vals['requisition_type'] != 'internal_transfer':
                vals['requisition_type'] = 'internal_transfer'
            elif parent.request_type == 'purchase_requisition' and vals['requisition_type'] != 'purchase_order':
                vals['requisition_type'] = 'purchase_order'
        
        return super(RequisitionOrderExtended, self).create(vals)

    def write(self, vals):
        """Update requisition_type if parent request_type changes and validate quantity and vendor selection"""
        # Validate quantity before write
        if 'quantity' in vals and vals.get('quantity', 0) <= 0:
            raise ValidationError('Quantity must be greater than 0. Please enter a valid quantity.')
        
        # Validate vendor selection: Only Purchase department can edit vendor in approved state
        if 'partner_id' in vals:
            for rec in self:
                if rec.requisition_product_id and rec.requisition_product_id.request_type == 'purchase_requisition':
                    parent_state = rec.requisition_product_id.state
                    # Vendor can only be edited in 'approved' state
                    if parent_state not in ['approved']:
                        raise ValidationError(
                            'Vendor can only be selected after the requisition is approved. '
                            'Current state: %s' % dict(rec.requisition_product_id._fields['state'].selection).get(parent_state, parent_state)
                        )
                    # Only Purchase department users can edit vendor
                    if not (self.env.user.has_group('purchase.group_purchase_user') or 
                            self.env.user.has_group('purchase.group_purchase_manager')):
                        raise ValidationError(
                            'Only Purchase department users can select vendors. '
                            'Please contact the Purchase department to assign a vendor.'
                        )
        
        result = super(RequisitionOrderExtended, self).write(vals)
        
        # If parent request_type changed, update requisition_type
        if 'requisition_product_id' in vals:
            for rec in self:
                if rec.requisition_product_id:
                    if rec.requisition_product_id.request_type == 'material_requisition':
                        rec.requisition_type = 'internal_transfer'
                    elif rec.requisition_product_id.request_type == 'purchase_requisition':
                        rec.requisition_type = 'purchase_order'
        
        # Also check if parent's request_type changed
        for rec in self:
            if rec.requisition_product_id:
                if rec.requisition_product_id.request_type == 'material_requisition' and rec.requisition_type != 'internal_transfer':
                    rec.requisition_type = 'internal_transfer'
                elif rec.requisition_product_id.request_type == 'purchase_requisition' and rec.requisition_type != 'purchase_order':
                    rec.requisition_type = 'purchase_order'
        
        return result

    # Override quantity field to set default value to 1, make it required, and prevent 0
    quantity = fields.Integer(
        string='Quantity', 
        help='Product quantity', 
        default=1,
        required=True
    )

    @api.constrains('quantity')
    def _check_quantity_positive(self):
        """Ensure quantity is greater than 0"""
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(
                    'Quantity must be greater than 0. Please enter a valid quantity for product: %s' % 
                    (rec.product_id.name if rec.product_id else 'Unknown Product')
                )

    @api.onchange('requisition_product_id')
    def _onchange_requisition_product_id(self):
        """Auto-set requisition_type based on parent request_type"""
        if self.requisition_product_id:
            if self.requisition_product_id.request_type == 'material_requisition':
                self.requisition_type = 'internal_transfer'
            elif self.requisition_product_id.request_type == 'purchase_requisition':
                self.requisition_type = 'purchase_order'
