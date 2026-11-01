import { SelectMeaningActivity } from "./SelectMeaningActivity";
import type { ActivityProps } from "./activity-utils";

/** Deletreo (§6.5): las letras en orden y la palabra escrita entre 4 opciones. */
export function SpellingActivity(props: ActivityProps) {
  return <SelectMeaningActivity {...props} />;
}
