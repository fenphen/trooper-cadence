namespace RestSharpTests.Models;

/// <summary>Mirror of the API's Carrier JSON. Property names match the camelCase JSON case-insensitively.</summary>
public class CarrierDto
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string McNumber { get; set; } = "";
    public int Rating { get; set; }
    public bool IsActive { get; set; }
}
