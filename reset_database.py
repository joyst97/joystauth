import sys
from server.database import (
    get_db, Developer, Application, User, License, AuditLog,
    Reseller, PlanKey, Blacklist, AppVariable, AppFile,
    AppNotification, SubscriptionTier
)
db = next(get_db())
print('Cleaning database...')
db.query(AuditLog).delete()
db.query(License).delete()
db.query(User).delete()
db.query(AppVariable).delete()
db.query(AppFile).delete()
db.query(AppNotification).delete()
db.query(Blacklist).delete()
db.query(SubscriptionTier).delete()
db.query(Reseller).delete()
db.query(PlanKey).delete()
db.query(Application).delete()
db.query(Developer).delete()
db.commit()
print('Database 100% Cleared & Reset to Zero!')
