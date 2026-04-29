# 存在重复元素

- Slug: `0004-contains-duplicate`
- ID: `0004`
- Difficulty: `easy`
- Topic: `数组`
- Default solution language: `java`
- Created: `2026-04-29T06:52:26Z`

## Problem

给定一个整数数组 `nums`，判断数组中是否存在任意两个不同下标 `i` 和 `j`，使得 `nums[i] == nums[j]`。

如果存在重复值返回 `true`，否则返回 `false`。

## Input

一个参数：

- `nums`: 整数数组。

## Output

返回一个布尔值：

- `true`：数组中存在重复元素。
- `false`：数组中不存在重复元素。

## Constraints

- `1 <= nums.length <= 10^5`
- `-10^9 <= nums[i] <= 10^9`

## Examples

```text
Input: nums = [1,2,3,1]
Output: true

Input: nums = [1,2,3,4]
Output: false

Input: nums = [1,1,1,3,3,4,3,2,4,2]
Output: true
```

## AI Notes

- Keep the reference solution separate from the user's active solution when generating one.
- Do not make the problem language-specific unless the user asked for that.
- Test cases should cover examples, boundaries, degenerate cases, adversarial cases, and randomized oracle-checked cases when practical.
