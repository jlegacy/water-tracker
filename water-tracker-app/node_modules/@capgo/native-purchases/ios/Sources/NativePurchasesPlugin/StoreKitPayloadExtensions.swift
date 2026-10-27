import Foundation
import StoreKit

extension Product.SubscriptionPeriod {
    var dictionary: [String: Any] {
        StoreKitPayloadHelpers.periodDictionary(unit: unit, value: value)
    }
}

extension Product.SubscriptionPeriod.Unit {
    var integerValue: Int {
        switch self {
        case .day:
            return 0
        case .week:
            return 1
        case .month:
            return 2
        case .year:
            return 3
        @unknown default:
            return -1
        }
    }

    var stringValue: String {
        switch self {
        case .day:
            return "day"
        case .week:
            return "week"
        case .month:
            return "month"
        case .year:
            return "year"
        @unknown default:
            return "unknown"
        }
    }
}

#if STOREKIT_26_5
@available(iOS 26.4, *)
internal extension Product.PurchaseOption {
    static func capacitorBillingPlanType(_ value: String) -> Product.PurchaseOption? {
        switch value {
        case "monthly":
            return .billingPlanType(.monthly)
        case "upFront":
            return .billingPlanType(.upFront)
        default:
            return nil
        }
    }
}

@available(iOS 26.4, *)
internal extension Product.SubscriptionInfo.BillingPlanType {
    var capacitorString: String {
        switch self {
        case .monthly:
            return "monthly"
        case .upFront:
            return "upFront"
        default:
            return "unknown"
        }
    }
}

@available(iOS 26.4, *)
internal extension Product.SubscriptionInfo.CommitmentInfo {
    var dictionary: [String: Any] {
        [
            "price": NSDecimalNumber(decimal: price).doubleValue,
            "priceString": displayPrice,
            "period": period.dictionary
        ]
    }
}

@available(iOS 26.4, *)
internal extension Product.SubscriptionInfo.PricingTerms {
    var dictionary: [String: Any] {
        [
            "billingPlanType": billingPlanType.capacitorString,
            "commitmentInfo": commitmentInfo.dictionary,
            "billingDisplayPrice": billingDisplayPrice,
            "billingPrice": NSDecimalNumber(decimal: billingPrice).doubleValue,
            "billingPeriod": billingPeriod.dictionary,
            "subscriptionOffers": subscriptionOffers.map {
                StoreKitPayloadHelpers.subscriptionOfferDictionary(from: $0)
            }
        ]
    }
}

@available(iOS 26.4, *)
internal extension Transaction.CommitmentInfo {
    var dictionary: [String: Any] {
        [
            "billingPeriodNumber": Int(billingPeriodNumber),
            "totalBillingPeriods": Int(totalBillingPeriods),
            "expirationDate": ISO8601DateFormatter().string(from: expirationDate),
            "price": NSDecimalNumber(decimal: price).doubleValue
        ]
    }
}

@available(iOS 26.4, *)
internal extension Product.SubscriptionInfo.RenewalInfo.CommitmentInfo {
    var dictionary: [String: Any] {
        [
            "autoRenewProductId": autoRenewPreference,
            "willAutoRenew": willAutoRenew,
            "renewalBillingPlanType": renewalBillingPlanType.capacitorString,
            "renewalDate": ISO8601DateFormatter().string(from: renewalDate),
            "renewalPrice": NSDecimalNumber(decimal: renewalPrice).doubleValue
        ]
    }
}
#endif
