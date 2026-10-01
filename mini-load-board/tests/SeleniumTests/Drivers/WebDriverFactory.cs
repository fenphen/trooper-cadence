using OpenQA.Selenium;
using OpenQA.Selenium.Chrome;

namespace SeleniumTests.Drivers;

/// <summary>
/// Creates the Chrome WebDriver used by every UI test.
///
/// Environment variables:
///   HEADLESS=true           run without a visible browser window (CI, or just faster)
///   CHROME_BINARY=/path     use a specific Chrome/Chromium executable instead of the system one
///   CHROMEDRIVER_PATH=/path use a specific chromedriver instead of letting Selenium Manager download one
/// </summary>
public static class WebDriverFactory
{
    public static IWebDriver CreateChrome()
    {
        var options = new ChromeOptions();

        // Headless by default in CI (GitHub Actions sets CI=true), opt-in locally.
        var headless = IsTruthy(Environment.GetEnvironmentVariable("HEADLESS"))
                       || IsTruthy(Environment.GetEnvironmentVariable("CI"));
        if (headless)
        {
            options.AddArgument("--headless=new");
        }

        // A fixed window size makes layouts (and screenshots) predictable.
        options.AddArgument("--window-size=1280,900");
        // Needed when Chrome runs as root inside a container (Docker, some CI runners).
        options.AddArgument("--no-sandbox");
        options.AddArgument("--disable-dev-shm-usage");
        options.AddArgument("--disable-gpu");

        var chromeBinary = Environment.GetEnvironmentVariable("CHROME_BINARY");
        if (!string.IsNullOrWhiteSpace(chromeBinary))
            options.BinaryLocation = chromeBinary;

        var driverPath = Environment.GetEnvironmentVariable("CHROMEDRIVER_PATH");
        IWebDriver driver;
        if (!string.IsNullOrWhiteSpace(driverPath))
        {
            // Explicit driver (useful in locked-down environments with no internet).
            var service = ChromeDriverService.CreateDefaultService(
                Path.GetDirectoryName(driverPath)!, Path.GetFileName(driverPath));
            service.SuppressInitialDiagnosticInformation = true;
            driver = new ChromeDriver(service, options);
        }
        else
        {
            // Default: Selenium Manager finds the installed Chrome and fetches a matching driver.
            driver = new ChromeDriver(options);
        }

        // We rely on explicit waits (WebDriverWait) everywhere, so keep the
        // implicit wait at zero - mixing the two leads to confusing timeouts.
        driver.Manage().Timeouts().ImplicitWait = TimeSpan.Zero;
        return driver;
    }

    private static bool IsTruthy(string? value) =>
        value is not null && (value.Equals("true", StringComparison.OrdinalIgnoreCase) || value == "1");
}
