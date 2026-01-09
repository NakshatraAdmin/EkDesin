# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PurchaseRequisitionExtended(models.Model):
    """Extended Employee Purchase Requisition with form-level request type"""
    _inherit = 'employee.purchase.requisition'

    # Step 1: Form-level request type field
    request_type = fields.Selection([
        ('material_requisition', 'Material Requisition'),
        ('purchase_requisition', 'Purchase Requisition')
    ], string='Request Type', required=True, default='material_requisition', 
       tracking=True, readonly=True, states={'new': [('readonly', False)]},
       help='Material Requisition: Internal stock movement only (Internal Transfer). Purchase Requisition: Can create both Purchase Order and Internal Transfer.')

    # Override employee_id to default to logged-in user's employee
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        default=lambda self: self.env.user.employee_id.id if self.env.user.employee_id else False,
        help='Select an employee'
    )

    # Update state field: Change "Purchase Order Created" to "Order Created"
    state = fields.Selection([
        ('new', 'New'),
        ('waiting_department_approval', 'Waiting Department Approval'),
        ('waiting_head_approval', 'Waiting Head Approval'),
        ('approved', 'Approved'),
        ('purchase_order_created', 'Order Created'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled')
    ], default='new', copy=False, tracking=True)

    @api.model
    def create(self, vals):
        """Override to validate PR creation permission and set defaults"""
        # Set default employee_id if not provided
        if 'employee_id' not in vals and self.env.user.employee_id:
            vals['employee_id'] = self.env.user.employee_id.id
        
        result = super(PurchaseRequisitionExtended, self).create(vals)
        
        # Step 2: Check PR creation permission
        if result.request_type == 'purchase_requisition':
            if not self.env.user.has_group('employee_requisition_extended.group_purchase_requisition_creator'):
                raise ValidationError(
                    'Only users with "Purchase Requisition Creator" access can create Purchase Requisitions. '
                    'Please contact your administrator.'
                )
        
        return result

    @api.onchange('request_type')
    def _onchange_request_type(self):
        """Update line types when request_type changes"""
        if self.request_type == 'material_requisition':
            # Update all existing lines to Material Requisition (internal_transfer)
            for line in self.requisition_order_ids:
                line.requisition_type = 'internal_transfer'
                
        elif self.request_type == 'purchase_requisition':
            # Update all existing lines to Purchase Requisition (purchase_order)
            for line in self.requisition_order_ids:
                line.requisition_type = 'purchase_order'

    def write(self, vals):
        """Override to validate PR creation on request_type change"""
        result = super(PurchaseRequisitionExtended, self).write(vals)
        
        # Update all child lines' requisition_type when parent request_type changes
        if 'request_type' in vals:
            for rec in self:
                # Update all existing lines to match new request_type
                if rec.request_type == 'material_requisition':
                    rec.requisition_order_ids.write({'requisition_type': 'internal_transfer'})
                elif rec.request_type == 'purchase_requisition':
                    rec.requisition_order_ids.write({'requisition_type': 'purchase_order'})
                
                # Validate PR creation permission
                if rec.request_type == 'purchase_requisition' and rec.state == 'new':
                    if not self.env.user.has_group('employee_requisition_extended.group_purchase_requisition_creator'):
                        raise ValidationError(
                            'Only users with "Purchase Requisition Creator" access can create Purchase Requisitions.'
                        )
        
        return result

    def action_confirm_requisition(self):
        """Override to set Production location (ID 15) as destination for Material Requisition"""
        # Call parent method first to set source_location_id and other fields
        super(PurchaseRequisitionExtended, self).action_confirm_requisition()
        
        # Override destination_location_id only for Material Requisition
        if self.request_type == 'material_requisition':
            # Set Production location (ID 15) as destination
            production_location = self.env['stock.location'].browse(15)
            if production_location.exists():
                self.destination_location_id = production_location.id
            else:
                # Fallback to original logic if location doesn't exist
                self.destination_location_id = (
                    self.employee_id.sudo().employee_location_id.id) if (
                    self.employee_id.sudo().employee_location_id) else (
                    self.env.ref('stock.stock_location_stock').id)
        # For Purchase Requisition, keep the original logic (already set by parent method)

    def action_create_purchase_order(self):
        """Step 3: Update create logic - MR creates Transfer only, PR creates both PO and Transfer"""
        # Check if request_type is set, if not use default or fallback
        if not self.request_type:
            # For backward compatibility with old records
            return super(PurchaseRequisitionExtended, self).action_create_purchase_order()
        
        if self.request_type == 'material_requisition':
            # MR: Only create Internal Transfer, NO PO
            for rec in self.requisition_order_ids:
                if rec.requisition_type == 'purchase_order':
                    raise ValidationError(
                        'Material Requisition cannot create Purchase Orders. '
                        'Only Internal Transfer is allowed for Material Requisitions.'
                    )
                # Create internal transfer only
                if rec.requisition_type == 'internal_transfer':
                    self.env['stock.picking'].create({
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id,
                        'picking_type_id': self.internal_picking_id.id,
                        'requisition_order': self.name,
                        'move_ids_without_package': [(0, 0, {
                            'name': rec.product_id.name,
                            'product_id': rec.product_id.id,
                            'product_uom': rec.product_id.uom_id.id,
                            'product_uom_qty': rec.quantity,
                            'location_id': self.source_location_id.id,
                            'location_dest_id': self.destination_location_id.id,
                        })]
                    })
            self.write({'state': 'purchase_order_created'})
            
        elif self.request_type == 'purchase_requisition':
            # PR: Create BOTH PO and Internal Transfer (can have both types of lines)
            po_created = False
            transfer_created = False
            
            for rec in self.requisition_order_ids:
                if rec.requisition_type == 'purchase_order':
                    # Create Purchase Order
                    if not rec.partner_id:
                        raise ValidationError('Please select a vendor for Purchase Order line: %s' % rec.product_id.name)
                    self.env['purchase.order'].create({
                        'partner_id': rec.partner_id.id,
                        'requisition_order': self.name,
                        "order_line": [(0, 0, {
                            'product_id': rec.product_id.id,
                            'product_qty': rec.quantity,
                        })]
                    })
                    po_created = True
                elif rec.requisition_type == 'internal_transfer':
                    # Create Internal Transfer
                    self.env['stock.picking'].create({
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id,
                        'picking_type_id': self.internal_picking_id.id,
                        'requisition_order': self.name,
                        'move_ids_without_package': [(0, 0, {
                            'name': rec.product_id.name,
                            'product_id': rec.product_id.id,
                            'product_uom': rec.product_id.uom_id.id,
                            'product_uom_qty': rec.quantity,
                            'location_id': self.source_location_id.id,
                            'location_dest_id': self.destination_location_id.id,
                        })]
                    })
                    transfer_created = True
            
            self.write({'state': 'purchase_order_created'})
        else:
            # Fallback to original logic if request_type not recognized
            return super(PurchaseRequisitionExtended, self).action_create_purchase_order()
