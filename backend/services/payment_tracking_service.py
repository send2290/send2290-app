"""Payment tracking service for reusing payments between preview and submission"""
import datetime
from models import SessionLocal, PaymentIntent
from services.audit_service import log_admin_action

class PaymentTrackingService:
    
    @staticmethod
    def record_payment_intent(payment_intent_id, user_uid, amount_cents=4500, status='succeeded'):
        """Record a new payment intent"""
        db = SessionLocal()
        try:
            # Check if payment intent already exists
            existing = db.query(PaymentIntent).filter(
                PaymentIntent.payment_intent_id == payment_intent_id
            ).first()
            
            if existing:
                # Update existing record
                existing.status = status
                existing.updated_at = datetime.datetime.utcnow()
                db.commit()
                return existing
            else:
                # Create new record
                payment_record = PaymentIntent(
                    payment_intent_id=payment_intent_id,
                    user_uid=user_uid,
                    amount_cents=amount_cents,
                    status=status
                )
                db.add(payment_record)
                db.commit()
                db.refresh(payment_record)
                return payment_record
                
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    @staticmethod
    def mark_used_for_preview(payment_intent_id, user_uid):
        """Mark a payment as used for preview"""
        db = SessionLocal()
        try:
            payment_record = db.query(PaymentIntent).filter(
                PaymentIntent.payment_intent_id == payment_intent_id,
                PaymentIntent.user_uid == user_uid
            ).first()
            
            if payment_record:
                payment_record.used_for_preview = 'true'
                payment_record.updated_at = datetime.datetime.utcnow()
                db.commit()
                
                log_admin_action("PAYMENT_USED_PREVIEW", 
                    f"Payment {payment_intent_id} marked as used for preview by user {user_uid}")
                return True
            return False
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    @staticmethod
    def mark_used_for_submission(payment_intent_id, user_uid, submission_id=None):
        """Mark a payment as used for submission"""
        db = SessionLocal()
        try:
            payment_record = db.query(PaymentIntent).filter(
                PaymentIntent.payment_intent_id == payment_intent_id,
                PaymentIntent.user_uid == user_uid
            ).first()
            
            if payment_record:
                payment_record.used_for_submission = 'true'
                if submission_id:
                    payment_record.submission_id = submission_id
                payment_record.updated_at = datetime.datetime.utcnow()
                db.commit()
                
                log_admin_action("PAYMENT_USED_SUBMISSION", 
                    f"Payment {payment_intent_id} marked as used for submission {submission_id} by user {user_uid}")
                return True
            return False
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    @staticmethod
    def can_reuse_payment(payment_intent_id, user_uid):
        """Check if a payment can be reused (exists, is successful, and belongs to user)"""
        db = SessionLocal()
        try:
            payment_record = db.query(PaymentIntent).filter(
                PaymentIntent.payment_intent_id == payment_intent_id,
                PaymentIntent.user_uid == user_uid,
                PaymentIntent.status == 'succeeded'
            ).first()
            
            return payment_record is not None
            
        except Exception as e:
            return False
        finally:
            db.close()
    
    @staticmethod
    def get_payment_usage(payment_intent_id, user_uid):
        """Get usage status of a payment"""
        db = SessionLocal()
        try:
            payment_record = db.query(PaymentIntent).filter(
                PaymentIntent.payment_intent_id == payment_intent_id,
                PaymentIntent.user_uid == user_uid
            ).first()
            
            if payment_record:
                return {
                    'used_for_preview': payment_record.used_for_preview == 'true',
                    'used_for_submission': payment_record.used_for_submission == 'true',
                    'submission_id': payment_record.submission_id,
                    'status': payment_record.status
                }
            return None
            
        except Exception as e:
            return None
        finally:
            db.close()
    
    @staticmethod
    def get_user_payments(user_uid):
        """Get all payments for a user"""
        db = SessionLocal()
        try:
            payments = db.query(PaymentIntent).filter(
                PaymentIntent.user_uid == user_uid
            ).order_by(PaymentIntent.created_at.desc()).all()
            
            return [{
                'payment_intent_id': p.payment_intent_id,
                'amount_cents': p.amount_cents,
                'status': p.status,
                'used_for_preview': p.used_for_preview == 'true',
                'used_for_submission': p.used_for_submission == 'true',
                'submission_id': p.submission_id,
                'created_at': p.created_at.isoformat() if p.created_at else None
            } for p in payments]
            
        except Exception as e:
            return []
        finally:
            db.close()
