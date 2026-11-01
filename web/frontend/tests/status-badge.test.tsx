import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { StatusBadge } from "../src/components/StatusBadge";

it("renders status with text instead of color alone", () => {
  render(<StatusBadge status="SUCCEEDED" />);
  expect(screen.getByText("已完成")).toBeVisible();
});
