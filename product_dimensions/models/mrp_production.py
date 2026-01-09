from odoo import models ,api,_,fields

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _get_moves_raw_values(self):
        moves = super()._get_moves_raw_values()

        for move_vals in moves:
            bom_line = move_vals.get('bom_line_id')
            if bom_line:
                bom_line = self.env['mrp.bom.line'].browse(bom_line)

                move_vals.update({
                    'show_dimensions': bom_line.show_dimensions,
                    'length': bom_line.length,
                    'width': bom_line.width,
                    'height': bom_line.height,
                    'sec_uom': bom_line.sec_uom,
                    'secondary_product_uom_qty': bom_line.secondary_product_uom_qty,
                })
        return moves

    def action_confirm(self):
        res = super().action_confirm()

        for mo in self:
            # --- Prepare MO move maps ---
            mo_moves_by_bom = {}
            mo_moves_by_product = {}

            for mo_move in mo.move_raw_ids:
                if mo_move.bom_line_id:
                    mo_moves_by_bom[mo_move.bom_line_id.id] = mo_move
                else:
                    # manual MO lines
                    mo_moves_by_product.setdefault(mo_move.product_id.id, []).append(mo_move)

            # --- Update Picking moves ---
            for picking in mo.picking_ids:
                for pick_move in picking.move_ids_without_package:

                    source_move = False

                    # 1️⃣ BOM-based matching
                    if pick_move.bom_line_id and pick_move.bom_line_id.id in mo_moves_by_bom:
                        source_move = mo_moves_by_bom[pick_move.bom_line_id.id]

                    # 2️⃣ Manual matching (product-based)
                    elif pick_move.product_id.id in mo_moves_by_product:
                        source_move = mo_moves_by_product[pick_move.product_id.id][0]

                    if not source_move:
                        continue

                    pick_move.write({
                        'show_dimensions': source_move.show_dimensions,
                        'length': source_move.length,
                        'width': source_move.width,
                        'height': source_move.height,
                        'assume_length': source_move.assume_height,
                        'assume_width': source_move.assume_height,
                        'assume_height': source_move.assume_height,

                        'sec_uom': source_move.sec_uom,
                        'secondary_product_uom_qty': source_move.secondary_product_uom_qty,
                    })

        return res

class StockMove(models.Model):
    _inherit = "stock.move"


    sec_uom = fields.Char(
        string="UoM", 
        readonly=True, default="ft²")
    
    secondary_product_uom_qty = fields.Float(
        string="Secondary Quantity",
        help="Secondary UoM Quantity",
        compute="_compute_secondary_product_uom_qty",
        store=True,
    )