### Zuora API Documentation
[API document](https://knowledgecenter.zuora.com/DC_Developers/G_SOAP_API/AB_Getting_started_with_the__SOAP_API)

### Required Parameters

1. User Name
2. Password
3. Endpoints

    1. Account
    2. Contact
    3. Credit Balance Adjustment
    4. Invoice
    5. Invoice Item
    6. Invoice Item Adjustment
    7. Payment
    8. Product
    9. Subscription

4. Backfill Mode

    *Note: Please enter Start and End date if Backfill mode is enabled. If not, extractor will automatically define date range to last 7 days. On the other hand, please avoid running backfill on multiple endpoints as there will be a possibility that it will flood the component's memory capacity. Please run 1 or 2 endpoint only when backfill mode is enabled.*
