import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCompactCurrency, formatPercent } from "@/lib/utils";
import type { ProductPerformance } from "@/types/api";

export function ProductTable({ title, products }: { title: string; products: ProductPerformance[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {products.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">No product data in range.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 pr-2 font-medium">Product</th>
                  <th className="pb-2 pr-2 text-right font-medium">Revenue</th>
                  <th className="pb-2 pr-2 text-right font-medium">Profit</th>
                  <th className="pb-2 text-right font-medium">Margin</th>
                </tr>
              </thead>
              <tbody>
                {products.map((product) => (
                  <tr key={product.product_ref} className="border-b last:border-0">
                    <td className="max-w-[220px] truncate py-2 pr-2 font-medium" title={product.name}>
                      {product.name}
                    </td>
                    <td className="py-2 pr-2 text-right tabular-nums">{formatCompactCurrency(product.revenue)}</td>
                    <td className={`py-2 pr-2 text-right tabular-nums ${product.profit < 0 ? "text-destructive" : ""}`}>
                      {formatCompactCurrency(product.profit)}
                    </td>
                    <td className="py-2 text-right tabular-nums">{formatPercent(product.margin_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
