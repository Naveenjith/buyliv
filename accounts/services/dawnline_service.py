from accounts.utils import get_user_status


def get_downline(user, max_level=10):
    result = []
    current_level_users = [user]

    for level in range(1, max_level + 1):
        next_level_users = []
        level_data = []

        for u in current_level_users:
            children = u.referrals.all()
            next_level_users.extend(children)

        if not next_level_users:
            break

        # 🔥 BUILD CLEAN RESPONSE (IMPORTANT)
        for child in next_level_users:
            level_data.append({
                "id": child.id,
                "user_id": child.user_id,
                "name": child.name,
                "phone": child.phone,

                # 🔥 CORRECT FLAGS
                "is_mlm_active": child.is_mlm_active,
                "is_wallet_active": child.is_wallet_active,
                "is_approved": child.is_approved,

                # 🔥 STATUS LABEL (UI READY)
                "status": get_user_status(child)
            })

        result.append({
            "level": level,
            "count": len(level_data),
            "users": level_data
        })

        current_level_users = next_level_users

    return result