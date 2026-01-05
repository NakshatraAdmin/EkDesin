dynamic_approval_purchase
=========================

This module extends the purchase workflow with a dynamic single-level and multi-level approval process.

Features
--------
- Adds approval request before confirming a Purchase Order.
- Supports primary and secondary approvers.
- Sends email and in-app notifications for approval.
- Restricts rfq actions until approved.
- Approval status visible on the Purchase Order.

Usage
-----
1. Set up approval rules for Purchase Orders.
2. When a rfq is created, an approval request is generated.
3. Approver receives a notification and can approve or reject the request.
4. Only approved orders can proceed to confirmation or rfq actions.

Credits
-------
Authors: 7Span

License
-------
LGPL-3.0 or later
