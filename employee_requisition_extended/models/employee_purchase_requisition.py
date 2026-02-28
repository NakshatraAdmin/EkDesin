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

    # Add many2many field for projects
    project_ids = fields.Many2many(
        comodel_name='project.project',
        string='Projects',
        help='Related projects for this requisition'
    )

    # Add One2many field to link to created Purchase Orders (RFQs)
    purchase_order_ids = fields.One2many(
        comodel_name='purchase.order',
        inverse_name='employee_requisition_id',
        string='Purchase Orders (RFQs)',
        help='Purchase Orders (RFQs) created from this requisition'
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

    # Computed field to determine if current user can mark as received
    can_receive = fields.Boolean(
        string='Can Receive',
        compute='_compute_can_receive',
        help='True if current user can mark this requisition as received'
    )

    @api.depends('state', 'request_type', 'confirm_id')
    def _compute_can_receive(self):
        """Compute if current user can mark requisition as received"""
        for rec in self:
            if rec.state != 'purchase_order_created':
                rec.can_receive = False
            elif rec.request_type == 'material_requisition':
                # For Material Requisition: Only creator can mark as received
                rec.can_receive = rec.confirm_id and rec.confirm_id.id == self.env.uid
            elif rec.request_type == 'purchase_requisition':
                # For Purchase Requisition: Only manager group can mark as received
                rec.can_receive = self.env.user.has_group('employee_purchase_requisition.employee_requisition_manager')
            else:
                # Fallback: use manager group
                rec.can_receive = self.env.user.has_group('employee_purchase_requisition.employee_requisition_manager')

    @api.model
    def create(self, vals):
        """Override to generate sequence based on request_type, validate PR creation permission and set defaults"""
        # Set default employee_id if not provided
        if 'employee_id' not in vals and self.env.user.employee_id:
            vals['employee_id'] = self.env.user.employee_id.id
        
        # Generate reference number based on request_type before calling super()
        # This ensures the name is set correctly before parent create() is called
        if vals.get('name', 'New') == 'New' or not vals.get('name'):
            request_type = vals.get('request_type', 'material_requisition')  # Default to material_requisition
            
            if request_type == 'material_requisition':
                # Use MR sequence for Material Requisition
                sequence_code = 'employee.material.requisition'
            elif request_type == 'purchase_requisition':
                # Use PR sequence for Purchase Requisition
                sequence_code = 'employee.purchase.requisition.extended'
            else:
                # Fallback to original sequence for backward compatibility
                sequence_code = 'employee.purchase.requisition'
            
            vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
        
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
        """Override to skip department approval and go directly to head approval, and set Production location for Material Requisition"""
        # Set location fields (from parent logic)
        self.source_location_id = (
            self.employee_id.sudo().department_id.department_location_id.id) if (
            self.employee_id.sudo().department_id.department_location_id) else (
            self.env.ref('stock.stock_location_stock').id)
        self.destination_location_id = (
            self.employee_id.sudo().employee_location_id.id) if (
            self.employee_id.sudo().employee_location_id) else (
            self.env.ref('stock.stock_location_stock').id)
        self.delivery_type_id = (
            self.source_location_id.warehouse_id.in_type_id.id)
        self.internal_picking_id = (
            self.source_location_id.warehouse_id.int_type_id.id)
        
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
        
        # Skip department approval - go directly to waiting_head_approval
        self.write({'state': 'waiting_head_approval'})
        self.confirm_id = self.env.uid
        self.confirmed_date = fields.Date.today()

    def action_department_approval(self):
        """Override to prevent department approval - workflow changed to single step"""
        raise ValidationError(
            'Department approval step has been removed. '
            'Requisitions now go directly from "New" to "Waiting Head Approval".'
        )

    def action_department_cancel(self):
        """Override to prevent department cancellation - workflow changed to single step"""
        raise ValidationError(
            'Department approval step has been removed. '
            'Requisitions now go directly from "New" to "Waiting Head Approval".'
        )

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
                    # Create PO with link back to requisition
                    po = self.env['purchase.order'].create({
                        'partner_id': rec.partner_id.id,
                        'requisition_order': self.name,  # Keep for backward compatibility
                        'employee_requisition_id': self.id,  # Link to requisition
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

    @api.depends('purchase_order_ids')
    def _compute_purchase_count(self):
        """Override to use new employee_requisition_id relationship"""
        for rec in self:
            # Use the new relationship if available, fallback to old method for backward compatibility
            if hasattr(rec, 'purchase_order_ids'):
                rec.purchase_count = len(rec.purchase_order_ids)
            else:
                # Fallback to original method
                rec.purchase_count = self.env['purchase.order'].search_count([
                    ('requisition_order', '=', rec.name)])

    def get_purchase_order(self):
        """Override Purchase order smart button view to use new relationship"""
        self.ensure_one()
        # Use the new relationship if available, fallback to old method for backward compatibility
        if hasattr(self, 'purchase_order_ids'):
            return {
                'type': 'ir.actions.act_window',
                'name': 'Purchase Orders (RFQs)',
                'view_mode': 'list,form',
                'res_model': 'purchase.order',
                'domain': [('employee_requisition_id', '=', self.id)],
                'context': {'default_employee_requisition_id': self.id}
            }
        else:
            # Fallback to original method
            return super(PurchaseRequisitionExtended, self).get_purchase_order()

    def action_receive(self):
        """Override to allow only creator to mark Material Requisition as received"""
        # For Material Requisition: Only the creator (confirm_id) can mark as received
        if self.request_type == 'material_requisition':
            if not self.confirm_id:
                raise ValidationError(
                    'Cannot mark as received: Creator information is missing. '
                    'Please contact your administrator.'
                )
            if self.confirm_id.id != self.env.uid:
                raise ValidationError(
                    'Only the person who created this Material Requisition can mark it as "Received". '
                    'You are not authorized to close this requisition.'
                )
        
        # For Purchase Requisition: Keep original behavior (Manager can mark as received)
        # Call parent method which allows manager group
        return super(PurchaseRequisitionExtended, self).action_receive()
