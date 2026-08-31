# Offline evaluation comparison

| Mode | Precision | Recall | F1 | Evidence coverage | Unsupported claims |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.5556 | 0.3846 | 0.4545 | 1.0000 | 4 |
| normalization_only | 0.6364 | 0.5385 | 0.5833 | 1.0000 | 4 |
| unverified_agent | 0.8125 | 1.0000 | 0.8966 | 1.0000 | 3 |
| removed_unsafe_recurrence | 0.0833 | 0.0769 | 0.0800 | 1.0000 | 11 |
| final | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |

All modes received the identical retained original transaction rows; no online model was called.
