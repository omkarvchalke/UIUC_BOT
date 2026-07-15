import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StudentTypeSelector } from "./StudentTypeSelector";

describe("StudentTypeSelector", () => {
  it("calls onSelect with the chosen student type", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<StudentTypeSelector onSelect={onSelect} isLoading={false} />);

    await user.click(screen.getByRole("button", { name: /freshman/i }));

    expect(onSelect).toHaveBeenCalledWith("freshman");
  });

  it("calls onSelect with null when skipped", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<StudentTypeSelector onSelect={onSelect} isLoading={false} />);

    await user.click(screen.getByRole("button", { name: /skip for now/i }));

    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("disables every option while isLoading is true", () => {
    render(<StudentTypeSelector onSelect={vi.fn()} isLoading={true} />);

    for (const name of [/freshman/i, /transfer/i, /graduate/i, /international/i, /skip/i]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
  });
});
