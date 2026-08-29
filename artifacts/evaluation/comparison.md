# Offline evaluation comparison

| Mode | Precision | Recall | F1 | Evidence coverage | Unsupported claims |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.6250 | 0.4167 | 0.5000 | 1.0000 | 3 |
| normalization_only | 0.7000 | 0.5833 | 0.6363 | 1.0000 | 3 |
| unverified_agent | 0.8000 | 1.0000 | 0.8889 | 1.0000 | 3 |
| removed_unsafe_recurrence | 0.8000 | 1.0000 | 0.8889 | 1.0000 | 3 |
| final | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |

All modes received the identical retained original transaction rows; no online model was called.
