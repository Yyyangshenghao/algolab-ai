"""Oracle for 0004-contains-duplicate."""


def oracle(*args, **kwargs):
    if args:
        nums = args[0]
    elif "nums" in kwargs:
        nums = kwargs["nums"]
    else:
        raise ValueError("containsDuplicate expects one list argument `nums`.")
    return len(nums) != len(set(nums))
